const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const Module = require('node:module');
const path = require('node:path');
const filename = path.resolve(__dirname, '../src/lib/utils.ts');
const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const compiled = new Module(filename, module);
compiled.filename = filename;
compiled.paths = module.paths;
compiled._compile(source, filename);
const linesToList = compiled.exports.linesToList ?? compiled.exports.csvToList; const listToLines = compiled.exports.listToLines ?? compiled.exports.listToCsv;
const items = ['Design, build, and test APIs', 'Coordinate releases'];
assert.deepEqual(linesToList(listToLines(items)), items);
assert.deepEqual(linesToList('  Design, build, and test APIs\n\n Coordinate releases  '), items);
console.log('List editing preserves commas and item boundaries.');

