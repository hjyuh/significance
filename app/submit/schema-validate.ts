import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import schema from "../../schema/record.schema.json";

// Imports the actual schema file — never a second copy, never drifts
// from the CLI's. Ajv2020 (not the default Ajv export, which is
// draft-07) because the schema declares
// "$schema": "https://json-schema.org/draft/2020-12/schema".
const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false, strictTypes: false });
addFormats(ajv);
const validateSchema = ajv.compile(schema);

export interface SchemaError {
  path: string;
  message: string;
  keyword: string;
}

export function validateAgainstSchema(record: unknown): SchemaError[] {
  const valid = validateSchema(record);
  if (valid) return [];
  return (validateSchema.errors ?? []).map((e) => ({
    path: e.instancePath || "$",
    message: e.message ?? "invalid",
    keyword: e.keyword,
  }));
}
