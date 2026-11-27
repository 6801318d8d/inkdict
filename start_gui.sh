#!/bin/sh
# Start the inkdict GUI on GNU/Linux and macOS: ./start_gui.sh
# It needs uv (https://docs.astral.sh/uv/), which installs Python 3.13 and the requirements by itself, and git.
cd "$(dirname "$0")" || exit 1

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is needed. Install it with:"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "then open a new terminal and run this script again."
    exit 1
fi
if ! command -v git >/dev/null 2>&1; then
    echo "git is needed (to install a dependency): install it with your package manager, then run this script again."
    exit 1
fi

# A uv-managed Python always comes with tkinter, which system Pythons often lack
export UV_PYTHON_PREFERENCE=only-managed
exec uv run --no-project --python 3.13 --with-requirements requirements.txt python -m wikidict.gui "$@"
