#!/bin/sh
# Build + axiom-audit phase: runs with --network none, resource limits, and
# a read-only root filesystem (see lean-adapter-untrusted-build.yml) --
# the only writable path is the bind-mounted /workspace/build-out (its
# size is polled and enforced by the workflow, not by Docker itself).
# Source is mounted read-only at /workspace/src; Lake needs a writable
# project directory to build into, so the first step copies the source
# into the writable output area rather than building it in place.
set -eu

trust_profile="lean_standard_classical"
target=""
while [ $# -gt 0 ]; do
  case "$1" in
    --trust-profile) trust_profile="$2"; shift 2 ;;
    --target) target="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

out=/workspace/build-out
log="$out/build.log"
: > "$log"

case "$trust_profile" in
  lean_standard_classical)
    allowlist="propext,Classical.choice,Quot.sound"
    ;;
  lean_standard_classical_plus_native)
    allowlist="propext,Classical.choice,Quot.sound,Lean.ofReduceBool"
    ;;
  custom)
    allowlist="${ALLOWLIST:-}"
    ;;
  *)
    echo "unknown trust profile: $trust_profile" >&2
    exit 1
    ;;
esac

executed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "executed_at=$executed_at" > "$out/build-result.env"

cp -r /workspace/src "$out/src"
cd "$out/src"

echo "== lake build ==" >> "$log"
build_result=passed
if ! lake build >> "$log" 2>&1; then
  build_result=failed
fi
echo "build_result=$build_result" >> "$out/build-result.env"

axiom_result=failed
if [ "$build_result" = passed ]; then
  if [ -z "$target" ]; then
    echo "no --target declaration given; cannot run an axiom audit" >> "$log"
  else
    echo "== #print axioms $target ==" >> "$log"
    printf '#print axioms %s\n' "$target" > /tmp/AxiomCheck.lean
    if lake env lean /tmp/AxiomCheck.lean >> "$log" 2>&1; then
      # `#print axioms` prints either "'decl' does not depend on any axioms"
      # or "'decl' depends on axioms: [a, b, c]". These are the only two
      # recognized outcomes; anything else (a future Lean version changing
      # this wording, an unexpected error) is NOT treated as "no axioms" --
      # axiom_result stays at its failed default so a format change fails
      # closed instead of silently passing.
      if grep -q 'does not depend on any axioms' "$log"; then
        axiom_result=passed
      elif grep -q 'depends on axioms' "$log"; then
        printed="$(grep 'depends on axioms' "$log" | tail -n1)"
        used="$(printf '%s' "$printed" | sed -n 's/.*\[\(.*\)\].*/\1/p' | tr -d ' ')"
        bad=""
        if [ -n "$used" ]; then
          old_ifs="$IFS"
          IFS=','
          for ax in $used; do
            case ",$allowlist," in
              *",$ax,"*) ;;
              *) bad="$bad $ax" ;;
            esac
          done
          IFS="$old_ifs"
        fi
        if [ -z "$bad" ]; then
          axiom_result=passed
        else
          echo "axioms outside the $trust_profile allowlist:$bad" >> "$log"
        fi
      else
        echo "could not parse #print axioms output; treating as a failing audit" >> "$log"
      fi
    fi
  fi
fi
echo "axiom_result=$axiom_result" >> "$out/build-result.env"
echo "allowlist=$allowlist" >> "$out/build-result.env"

if [ -f lake-manifest.json ]; then
  lockfile_hash="$(sha256sum lake-manifest.json | cut -d' ' -f1)"
else
  lockfile_hash=""
  echo "no lake-manifest.json found; lockfile_hash left empty" >> "$log"
fi
echo "lockfile_hash=$lockfile_hash" >> "$out/build-result.env"

[ "$build_result" = passed ] && [ "$axiom_result" = passed ]
