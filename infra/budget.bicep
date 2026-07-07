// Subscription-scope monthly cost budget with email alerts.
// Deploy:  az deployment sub create --name budget-alert --location centralus --template-file infra/budget.bicep
// Verify:  az consumption budget list
// A budget never stops or blocks spend — it only alerts. The pause/resume
// bracket (project doc §5) is what actually caps cost.
targetScope = 'subscription'

param budgetName string = 'gutenberg-fingerprint-monthly'

@description('Monthly cap in USD. F2 left running 24/7 burns ~$263/mo; with the pause bracket working, real spend should sit far under this.')
param amount int = 50

param startDate string = '2026-07-01'
param endDate string = '2036-07-01'

@description('Up to 5 recipients.')
param contactEmails array = [
  'sam.vanwilligen@gmail.com'
]

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
      endDate: endDate
    }
    notifications: {
      Actual50Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      Actual90Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 90
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      Forecast100Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: contactEmails
      }
    }
  }
}

output resourceId string = budget.id
