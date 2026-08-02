import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import schema from "../../schema/record.schema.json";

// Ajv compiles a schema into a validator via `new Function(...)` at
// compile time. Cloudflare Workers' SSR sandbox (this app's dev/prod
// render environment, via @cloudflare/vite-plugin) disallows dynamic
// code generation, so compilation must never run during server-side
// rendering — only in a real browser, after hydration. During SSR this
// returns no errors; the client re-runs it for real once mounted, and
// since this component is entirely client-driven (`useState`), nothing
// treats the transient SSR-time result as final.
type CompiledValidator = ReturnType<Ajv2020["compile"]>;

let validateSchema: CompiledValidator | null = null;

function compileValidator(): CompiledValidator {
  const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false, strictTypes: false });
  addFormats(ajv);
  return ajv.compile(schema);
}

function getValidator() {
  if (typeof window === "undefined") return null;
  if (!validateSchema) {
    validateSchema = compileValidator();
  }
  return validateSchema;
}

export interface SchemaError {
  path: string;
  message: string;
  keyword: string;
}

function collectSchemaErrors(validate: CompiledValidator, record: unknown): SchemaError[] {
  const valid = validate(record);
  if (valid) return [];
  return (validate.errors ?? []).map((e) => ({
    path: e.instancePath || "$",
    message: e.message ?? "invalid",
    keyword: e.keyword,
  }));
}

export function validateAgainstSchema(record: unknown): SchemaError[] {
  const validate = getValidator();
  if (!validate) return [];
  return collectSchemaErrors(validate, record);
}

/**
 * Exercises the same Ajv compilation and validation path without relying on a
 * browser global. This is intentionally called by tests, never during SSR.
 */
export function validateAgainstSchemaNow(record: unknown): SchemaError[] {
  return collectSchemaErrors(compileValidator(), record);
}
