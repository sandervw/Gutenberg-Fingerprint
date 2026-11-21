// 8-bit fire that lights a heading's letters left to right.

const cellSize = 4;
const levels = 8;
const tickMilliseconds = 42;
const cooling = { base: 0.06, spread: 0.12 };
const burnMilliseconds = 520;
const settleMilliseconds = 1600;
const padSide = 10;
const padTop = 56;
const padBottom = 6;
const stops = [
	[0, 20, 2, 2],
	[0.12, 70, 10, 6],
	[0.28, 140, 26, 8],
	[0.45, 205, 62, 10],
	[0.6, 240, 112, 16],
	[0.75, 255, 165, 34],
	[0.88, 255, 218, 90],
	[1, 255, 250, 215]
];

/** Fire colours from ember to white-hot; index 0 is transparent. */
function paletteOf(levelCount) {
	const palette = [null];
	for (let level = 1; level <= levelCount; level += 1) {
		const share = level / levelCount;
		const upper = stops.findIndex((stop) => stop[0] >= share);
		const below = stops[Math.max(0, upper - 1)];
		const above = stops[upper];
		const span = above[0] - below[0];
		const fraction = span === 0 ? 0 : (share - below[0]) / span;
		palette.push([1, 2, 3].map((channel) => Math.round(below[channel] + (above[channel] - below[channel]) * fraction)));
	}
	return palette;
}

const palette = paletteOf(levels);

/** A pixelated canvas covering the heading plus room for flames. */
function fireCanvas(headingBox) {
	const canvas = document.createElement('canvas');
	canvas.className = 'fire';
	canvas.setAttribute('aria-hidden', 'true');
	canvas.width = Math.ceil((headingBox.width + padSide * 2) / cellSize);
	canvas.height = Math.ceil((headingBox.height + padTop + padBottom) / cellSize);
	canvas.style.left = `${-padSide}px`;
	canvas.style.top = `${-padTop}px`;
	canvas.style.width = `${canvas.width * cellSize}px`;
	canvas.style.height = `${canvas.height * cellSize}px`;
	return canvas;
}

/** The cells a letter's lower body covers, where its flames start. */
function cellBox(letterBox, headingBox, field) {
	const left = (letterBox.left - headingBox.left + padSide) / cellSize;
	const right = (letterBox.right - headingBox.left + padSide) / cellSize;
	const top = (letterBox.top - headingBox.top + padTop + letterBox.height * 0.55) / cellSize;
	const bottom = (letterBox.bottom - headingBox.top + padTop - letterBox.height * 0.12) / cellSize;
	return {
		left: Math.max(0, Math.floor(left)),
		right: Math.min(field.columns - 1, Math.ceil(right)),
		top: Math.max(0, Math.floor(top)),
		bottom: Math.min(field.rows - 1, Math.ceil(bottom))
	};
}

/** Scatter fresh heat over a letter's cells. */
function seed(field, box, chance) {
	for (let row = box.top; row <= box.bottom; row += 1) {
		for (let column = box.left; column <= box.right; column += 1) {
			if (Math.random() >= chance) continue;
			const cell = row * field.columns + column;
			field.heat[cell] = Math.max(field.heat[cell], 0.7 + Math.random() * 0.3);
		}
	}
}

/** Light letters whose time has come; true while any still burns. */
function igniteLetters(letters, field, elapsed) {
	let burning = false;
	letters.forEach((letter, index) => {
		const age = elapsed - (index / Math.max(1, letters.length - 1)) * field.sweep;
		if (age >= 0) letter.element.classList.add('lit');
		if (age < 0 || age >= burnMilliseconds) return;
		burning = true;
		seed(field, letter.box, 0.32 * (1 - age / burnMilliseconds));
	});
	return burning;
}

/** Move heat up one cell, cooling it; return the hottest cell. */
function rise(field) {
	const { columns, rows, heat, next } = field;
	let hottest = 0;
	for (let row = 0; row < rows; row += 1) {
		for (let column = 0; column < columns; column += 1) {
			const drift = Math.min(columns - 1, Math.max(0, column + Math.floor(Math.random() * 3) - 1));
			const below = row + 1 < rows ? heat[(row + 1) * columns + drift] : 0;
			const cell = row * columns + column;
			const cooled = below - (cooling.base + Math.random() * cooling.spread);
			const value = Math.max(heat[cell] * 0.3, cooled);
			next[cell] = value > 0.04 ? value : 0;
			hottest = Math.max(hottest, next[cell]);
		}
	}
	field.heat = next;
	field.next = heat;
	return hottest;
}

/** Paint heat into image pixels through the 8-colour palette. */
function paint(image, heat) {
	const pixels = image.data;
	heat.forEach((value, cell) => {
		const offset = cell * 4;
		const level = Math.min(levels, Math.floor(value * (levels + 1)));
		const colour = palette[level];
		if (!colour) {
			pixels[offset + 3] = 0;
			return;
		}
		pixels.set(colour, offset);
		pixels[offset + 3] = level < levels / 4 ? 110 + level * (145 / (levels / 4)) : 255;
	});
}

/** Burn in a heading's `.letter` spans once, left to right. */
export function burnTitle(heading) {
	const headingBox = heading.getBoundingClientRect();
	const canvas = fireCanvas(headingBox);
	const cells = canvas.width * canvas.height;
	const elements = [...heading.querySelectorAll('.letter')];
	const field = {
		columns: canvas.width,
		rows: canvas.height,
		heat: new Float32Array(cells),
		next: new Float32Array(cells),
		sweep: Math.min(2200, 450 + elements.length * 55)
	};
	const letters = elements.map((element) => ({
		element,
		box: cellBox(element.getBoundingClientRect(), headingBox, field)
	}));
	const context = canvas.getContext('2d');
	const image = context.createImageData(field.columns, field.rows);
	heading.append(canvas);
	heading.classList.add('burning');
	// Once cooled, drop the animation so the title follows theme changes.
	setTimeout(() => heading.classList.remove('burning'), field.sweep + 1500);
	const start = performance.now();

	/** One fire step: ignite, rise, paint, then schedule or stop. */
	function frame() {
		const elapsed = performance.now() - start;
		const burning = igniteLetters(letters, field, elapsed);
		const hottest = rise(field);
		paint(image, field.heat);
		context.putImageData(image, 0, 0);
		const isDone = elapsed > field.sweep + burnMilliseconds + settleMilliseconds;
		const isActive = burning || hottest > 0.05 || elapsed < field.sweep;
		if (isDone || !isActive) {
			elements.forEach((element) => element.classList.add('lit'));
			canvas.remove();
			return;
		}
		setTimeout(frame, tickMilliseconds);
	}
	frame();
}
