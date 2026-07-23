// Nightly capacity bracket - FULL LOOP.
// Creates: a custom "pause/resume" role, a Logic App with a managed identity,
// and the assignment binding that identity to the role on the F2 capacity.
// The Logic App runs the whole nightly bracket:
//   resume -> wait Active -> run pl_nightly -> wait done -> deploy hook -> poll Pages build -> suspend
// Suspend runs regardless of upstream outcome, so the capacity is never left on.
//
// Deploy into the SAME resource group as the F2 capacity (secrets passed at deploy time):
//   az deployment group create -g <capacity-rg> --template-file infra/pipeline-automation.bicep \
//     --parameters capacityName=gbfabric deployHookUrl='<hook url>' cfApiToken='<pages read token>'
// Prereqs the identity needs: Fabric tenant setting "Service principals can use Fabric APIs"
// enabled, and the identity granted Contributor on the workspace.
targetScope = 'resourceGroup'

@description('Name of the paid F2 Fabric capacity, as it appears in the Azure portal.')
param capacityName string

param location string = resourceGroup().location
param logicAppName string = 'la-gutenberg-nightly'

@description('Hour of day (0-23) for the nightly run, in the timeZone below.')
param nightlyHour int = 3

@description('Windows time zone name, e.g. "W. Europe Standard Time". UTC by default.')
param timeZone string = 'UTC'

@description('Enabled = the nightly schedule fires. The full bracket suspends at the end, so leaving this on is safe.')
@allowed([ 'Enabled', 'Disabled' ])
param workflowState string = 'Enabled'

param fabricWorkspaceId string = 'bfad3948-6e3b-4eeb-8ee1-485e0f47c87b'
param pipelineItemId string = 'e5d7c062-78d2-441d-b274-0329cacab9be'
param cloudflareAccountId string = '954c30f428e0a61f4c66e6a679f51ec0'
param pagesProjectName string = 'gutenberg-fingerprint'

@description('Cloudflare Pages deploy-hook URL. Secret - a POST to it triggers the site rebuild.')
@secure()
param deployHookUrl string

@description('Cloudflare API token (Account > Cloudflare Pages > Read). Used to poll deployment status.')
@secure()
param cfApiToken string

// The capacity already exists (created by hand in the portal); we only reference it.
resource capacity 'Microsoft.Fabric/capacities@2023-11-01' existing = {
  name: capacityName
}

// Custom role: exactly the four actions the bracket needs, nothing more.
resource pauseResumeRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'fabric-capacity-pause-resume')
  properties: {
    roleName: 'Fabric Capacity Pause-Resume (gutenberg)'
    description: 'Read/write plus suspend and resume on Fabric capacities. For the nightly automation identity.'
    type: 'CustomRole'
    assignableScopes: [
      resourceGroup().id
    ]
    permissions: [
      {
        actions: [
          'Microsoft.Fabric/capacities/read'
          'Microsoft.Fabric/capacities/write'
          'Microsoft.Fabric/capacities/suspend/action'
          'Microsoft.Fabric/capacities/resume/action'
        ]
        notActions: []
      }
    ]
  }
}

// The orchestrator. System-assigned identity = an auto-managed service principal
// that the role assignment below grants power over the capacity, and that a Fabric
// workspace Contributor grant lets trigger pl_nightly.
resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: logicAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: workflowState
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        deployHookUrl: {
          type: 'securestring'
        }
        cfApiToken: {
          type: 'securestring'
        }
      }
      triggers: {
        Nightly: {
          type: 'Recurrence'
          recurrence: {
            frequency: 'Day'
            interval: 1
            timeZone: timeZone
            schedule: {
              hours: [ nightlyHour ]
              minutes: [ 0 ]
            }
          }
        }
      }
      actions: {
        // 1. Wake the capacity.
        Resume_capacity: {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: 'https://management.azure.com${capacity.id}/resume?api-version=2023-11-01'
            authentication: {
              type: 'ManagedServiceIdentity'
              audience: 'https://management.azure.com'
            }
          }
        }
        // 2. Poll until it reports Active before doing any Fabric work.
        Until_Active: {
          type: 'Until'
          runAfter: {
            Resume_capacity: [ 'Succeeded' ]
          }
          expression: '@equals(body(\'Get_capacity_state\')?[\'properties\']?[\'state\'], \'Active\')'
          limit: {
            count: 20
            timeout: 'PT15M'
          }
          actions: {
            Wait_30s: {
              type: 'Wait'
              inputs: {
                interval: {
                  count: 30
                  unit: 'Second'
                }
              }
            }
            Get_capacity_state: {
              type: 'Http'
              runAfter: {
                Wait_30s: [ 'Succeeded' ]
              }
              inputs: {
                method: 'GET'
                uri: 'https://management.azure.com${capacity.id}?api-version=2023-11-01'
                authentication: {
                  type: 'ManagedServiceIdentity'
                  audience: 'https://management.azure.com'
                }
              }
            }
          }
        }
        // 3a. Claim pipeline ownership as this identity, so the identity-triggered run can
        // acquire a token (fixes UserAccessTokenException "unable to acquire user token").
        Claim_owner: {
          type: 'Http'
          runAfter: {
            Until_Active: [ 'Succeeded' ]
          }
          inputs: {
            method: 'PATCH'
            uri: 'https://api.fabric.microsoft.com/v1/workspaces/${fabricWorkspaceId}/dataPipelines/${pipelineItemId}'
            authentication: {
              type: 'ManagedServiceIdentity'
              audience: 'https://api.fabric.microsoft.com'
            }
            body: {
              description: 'Owned by la-gutenberg-nightly (nightly automation)'
            }
          }
        }
        // 3b. Kick pl_nightly. DisableAsyncPattern so we keep the 202 + Location header.
        Run_pipeline: {
          type: 'Http'
          runAfter: {
            Claim_owner: [ 'Succeeded' ]
          }
          operationOptions: 'DisableAsyncPattern'
          inputs: {
            method: 'POST'
            uri: 'https://api.fabric.microsoft.com/v1/workspaces/${fabricWorkspaceId}/items/${pipelineItemId}/jobs/instances?jobType=Pipeline'
            authentication: {
              type: 'ManagedServiceIdentity'
              audience: 'https://api.fabric.microsoft.com'
            }
          }
        }
        // 4. Poll the job instance (Location header) until it reaches a terminal state.
        Until_pipeline_done: {
          type: 'Until'
          runAfter: {
            Run_pipeline: [ 'Succeeded' ]
          }
          expression: '@contains(createArray(\'Completed\',\'Failed\',\'Cancelled\',\'Deduped\'), coalesce(body(\'Get_job_status\')?[\'status\'], \'\'))'
          limit: {
            count: 90
            timeout: 'PT90M'
          }
          actions: {
            Wait_60s: {
              type: 'Wait'
              inputs: {
                interval: {
                  count: 60
                  unit: 'Second'
                }
              }
            }
            Get_job_status: {
              type: 'Http'
              runAfter: {
                Wait_60s: [ 'Succeeded' ]
              }
              inputs: {
                method: 'GET'
                uri: '@{outputs(\'Run_pipeline\')?[\'headers\']?[\'Location\']}'
                authentication: {
                  type: 'ManagedServiceIdentity'
                  audience: 'https://api.fabric.microsoft.com'
                }
              }
            }
          }
        }
        // 4b. Read the final job status at top level (reliable outside the Until scope).
        Get_job_status_final: {
          type: 'Http'
          runAfter: {
            Until_pipeline_done: [ 'Succeeded', 'Failed', 'TimedOut' ]
          }
          inputs: {
            method: 'GET'
            uri: '@{outputs(\'Run_pipeline\')?[\'headers\']?[\'Location\']}'
            authentication: {
              type: 'ManagedServiceIdentity'
              audience: 'https://api.fabric.microsoft.com'
            }
          }
        }
        // 5. Only rebuild the site if the pipeline actually completed.
        Condition_pipeline_ok: {
          type: 'If'
          runAfter: {
            Get_job_status_final: [ 'Succeeded', 'Failed', 'TimedOut', 'Skipped' ]
          }
          expression: {
            and: [
              {
                equals: [ '@body(\'Get_job_status_final\')?[\'status\']', 'Completed' ]
              }
            ]
          }
          actions: {
            Deploy_hook: {
              type: 'Http'
              inputs: {
                method: 'POST'
                uri: '@parameters(\'deployHookUrl\')'
              }
            }
            // Poll the newest Pages deployment until the build lands.
            Until_build_done: {
              type: 'Until'
              runAfter: {
                Deploy_hook: [ 'Succeeded' ]
              }
              expression: '@contains(createArray(\'success\',\'failure\',\'canceled\',\'skipped\'), coalesce(first(body(\'Get_deployment\')?[\'result\'])?[\'latest_stage\']?[\'status\'], \'\'))'
              limit: {
                count: 40
                timeout: 'PT20M'
              }
              actions: {
                Wait_15s: {
                  type: 'Wait'
                  inputs: {
                    interval: {
                      count: 15
                      unit: 'Second'
                    }
                  }
                }
                Get_deployment: {
                  type: 'Http'
                  runAfter: {
                    Wait_15s: [ 'Succeeded' ]
                  }
                  inputs: {
                    method: 'GET'
                    uri: 'https://api.cloudflare.com/client/v4/accounts/${cloudflareAccountId}/pages/projects/${pagesProjectName}/deployments'
                    queries: {
                      per_page: '1'
                    }
                    headers: {
                      Authorization: 'Bearer @{parameters(\'cfApiToken\')}'
                    }
                  }
                }
              }
            }
          }
          else: {
            actions: {}
          }
        }
        // 6. Always suspend, whatever happened above - the capacity is never left on.
        Suspend_capacity: {
          type: 'Http'
          runAfter: {
            Condition_pipeline_ok: [ 'Succeeded', 'Failed', 'Skipped', 'TimedOut' ]
          }
          inputs: {
            method: 'POST'
            uri: 'https://management.azure.com${capacity.id}/suspend?api-version=2023-11-01'
            authentication: {
              type: 'ManagedServiceIdentity'
              audience: 'https://management.azure.com'
            }
          }
        }
      }
      outputs: {}
    }
    parameters: {
      deployHookUrl: {
        value: deployHookUrl
      }
      cfApiToken: {
        value: cfApiToken
      }
    }
  }
}

// Bind the Logic App's identity to the custom role, scoped to the capacity only.
resource assignRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(capacity.id, logicApp.id, pauseResumeRole.id)
  scope: capacity
  properties: {
    roleDefinitionId: pauseResumeRole.id
    principalId: logicApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output logicAppPrincipalId string = logicApp.identity.principalId
output roleDefinitionId string = pauseResumeRole.id
