# shellcheck shell=sh
# Put npm/npx on PATH, for scripts that run under a non-interactive shell.
#
# nvm is a shell function loaded from an interactive profile, so `npm` is simply absent
# from a `make` recipe or a launchd job even though node is installed. Without this,
# `make verify-frontend` died with exit 127 while `verify-backend` had already printed
# green — the frontend half of the gate silently not running against a repo whose third
# golden rule is that verify gates every commit.
#
# Resolution order: whatever is already on PATH wins, then nvm's `default` alias, then the
# highest installed nvm version. Sourced (not executed) by both run.sh and the Makefile, so
# a missing npm `exit 127`s the caller — loudly — rather than skipping the step.

_beacon_npm_bin() {
    _nvm_dir="${NVM_DIR:-$HOME/.nvm}"
    _default_alias=""
    [ -f "$_nvm_dir/alias/default" ] && _default_alias="$(cat "$_nvm_dir/alias/default")"
    _fallback=""
    # Highest version first, so the first executable npm is also the newest.
    for _dir in $(find "$_nvm_dir/versions/node" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort -Vr); do
        [ -x "$_dir/bin/npm" ] || continue
        if [ -n "$_default_alias" ]; then
            case "${_dir##*/}" in
                "v$_default_alias"*) printf '%s\n' "$_dir/bin"; return 0 ;;
            esac
        fi
        [ -z "$_fallback" ] && _fallback="$_dir/bin"
    done
    [ -n "$_fallback" ] || return 1
    printf '%s\n' "$_fallback"
}

if ! command -v npm >/dev/null 2>&1; then
    _npm_bin="$(_beacon_npm_bin)" || {
        echo "npm not found: install Node (e.g. \`nvm install --lts\`) or put npm on PATH" >&2
        exit 127
    }
    PATH="$_npm_bin:$PATH"
    export PATH
    unset _npm_bin
fi
