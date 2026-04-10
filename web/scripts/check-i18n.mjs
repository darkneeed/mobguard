import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function loadDictionary(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const match = source.match(/export const \w+Dictionary: TranslationDictionary = (\{[\s\S]*\});\s*$/);
  if (!match) {
    throw new Error(`Failed to parse dictionary: ${filePath}`);
  }
  return Function(`return (${match[1]});`)();
}

function collectKeys(value, prefix = "") {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [prefix].filter(Boolean);
  }
  return Object.entries(value).flatMap(([key, nested]) =>
    collectKeys(nested, prefix ? `${prefix}.${key}` : key)
  );
}

const ru = loadDictionary(path.join(root, "src", "localization", "dictionaries", "ru.ts"));
const en = loadDictionary(path.join(root, "src", "localization", "dictionaries", "en.ts"));

const ruKeys = new Set(collectKeys(ru));
const enKeys = new Set(collectKeys(en));

const onlyRu = [...ruKeys].filter((key) => !enKeys.has(key));
const onlyEn = [...enKeys].filter((key) => !ruKeys.has(key));

if (onlyRu.length || onlyEn.length) {
  if (onlyRu.length) {
    console.error("Missing in en:");
    console.error(onlyRu.join("\n"));
  }
  if (onlyEn.length) {
    console.error("Missing in ru:");
    console.error(onlyEn.join("\n"));
  }
  process.exit(1);
}

console.log(`i18n parity OK (${ruKeys.size} keys)`);
