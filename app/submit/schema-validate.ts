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
let validateSchema: ReturnType<Ajv2020["compile"]> | null = null;

function getValidator() {
  if (typeof window === "undefined") return null;
  if (!validateSchema) {
    const ajv = new Ajv2020({ allErrors: true, strict: true, strictRequired: false, strictTypes: false });
    addFormats(ajv);
    validateSchema = ajv.compile(schema);
  }
  return validateSchema;
}

export interface SchemaError {
  path: string;
  message: string;
  keyword: string;
}

export function validateAgainstSchema(record: unknown): SchemaError[] {
  const validate = getValidator();
  if (!validate) return [];
  const valid = validate(record);
  if (valid) return [];
  return (validate.errors ?? []).map((e) => ({
    path: e.instancePath || "$",
    message: e.message ?? "invalid",
    keyword: e.keyword,
  }));
}
