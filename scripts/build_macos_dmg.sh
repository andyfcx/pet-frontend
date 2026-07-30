#!/bin/zsh

set -euo pipefail

APP_NAME="Biometeo Frontend"
APP_BUNDLE="${APP_NAME}.app"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist"
BUILD_DIR="${PROJECT_ROOT}/build"
SPEC_FILE="${PROJECT_ROOT}/run.spec"
PYTHON_VERSION="${PYTHON_VERSION:-3.13}"
TARGET_ARCH="${TARGET_ARCH:-arm64}"
DMG_VOLUME_NAME="${DMG_VOLUME_NAME:-${APP_NAME}}"
VERSION="$(
  /usr/bin/awk -F'"' '/^version = / { print $2; exit }' "${PROJECT_ROOT}/pyproject.toml"
)"
DMG_NAME="${APP_NAME// /-}-${VERSION}-macos-${TARGET_ARCH}.dmg"
DMG_PATH="${DIST_DIR}/${DMG_NAME}"
STAGING_DIR="${BUILD_DIR}/dmg-${TARGET_ARCH}"
VENV_DIR="${PROJECT_ROOT}/.venv-dmg-${TARGET_ARCH}"

case "${TARGET_ARCH}" in
  arm64|x86_64) ;;
  *)
    echo "Unsupported TARGET_ARCH: ${TARGET_ARCH}. Use arm64 or x86_64." >&2
    exit 1
    ;;
esac

UV_ARCH="${TARGET_ARCH}"
if [[ "${TARGET_ARCH}" == "arm64" ]]; then
  UV_ARCH="aarch64"
fi

PYTHON_REQUEST="cpython-${PYTHON_VERSION}-macos-${UV_ARCH}-none"
# --managed-python forces uv's own downloaded CPython (self-contained Tcl/Tk)
# instead of a system interpreter (e.g. Homebrew's python@3.13, which ships
# without a working tkinter unless python-tk is separately installed). Using
# the system interpreter silently produces a build with tkinter excluded,
# which crashes at startup with "ModuleNotFoundError: No module named 'tkinter'".
PYTHON_BIN="$(uv python find --managed-python "${PYTHON_REQUEST}" 2>/dev/null || true)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script must run on macOS." >&2
  exit 1
fi

for cmd in uv hdiutil codesign; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 1
  fi
done

HOST_ARCH="$(uname -m)"

if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
  echo "Installing uv-managed Python ${PYTHON_VERSION} for ${TARGET_ARCH}"
  uv python install --managed-python "${PYTHON_REQUEST}"
fi

PYTHON_BIN="$(uv python find --managed-python "${PYTHON_REQUEST}")"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Expected Python interpreter not found at ${PYTHON_BIN}" >&2
  exit 1
fi

PYTHON_ARCH="$(file "${PYTHON_BIN}")"

if [[ "${HOST_ARCH}" == "x86_64" && "${TARGET_ARCH}" == "arm64" ]]; then
  echo "Building arm64 DMGs requires an arm64 macOS environment." >&2
  exit 1
fi

if [[ "${PYTHON_ARCH}" != *"${TARGET_ARCH}"* && "${PYTHON_ARCH}" != *"universal"* ]]; then
  echo "python${PYTHON_VERSION} does not support target architecture ${TARGET_ARCH}." >&2
  echo "Interpreter details: ${PYTHON_ARCH}" >&2
  exit 1
fi

UV_PIP_RUNNER=(uv pip install --python "${VENV_DIR}/bin/python")
PYINSTALLER_RUNNER=("${VENV_DIR}/bin/pyinstaller")

if [[ "${TARGET_ARCH}" == "x86_64" && "${HOST_ARCH}" == "arm64" ]]; then
  if ! /usr/bin/arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
    echo "Rosetta 2 is required to build x86_64 packages on Apple Silicon." >&2
    exit 1
  fi
fi

echo "Creating build virtualenv with Python ${PYTHON_VERSION}"
rm -rf "${VENV_DIR}"
uv venv --python "${PYTHON_BIN}" "${VENV_DIR}"

NUMPY_TARGET_PLATFORM="x86_64-apple-darwin"
if [[ "${TARGET_ARCH}" == "arm64" ]]; then
  NUMPY_TARGET_PLATFORM="aarch64-apple-darwin"
fi

# NumPy >=2.0 publishes two macOS wheels per architecture: an older one
# (tagged macosx_10_13/11_0) and a newer one (tagged macosx_14_0) that links
# Apple Accelerate's "new LAPACK" ILP64 symbols, which only exist on macOS
# >=13.3. Our GitHub Actions runners are themselves newer than 13.3, so a
# plain `uv pip install` picks the newer tag by default, silently raising the
# app's real minimum macOS version above LSMinimumSystemVersion and crashing
# with "Symbol not found: _cblas_caxpy$NEWLAPACK$ILP64" on older Macs.
# Installing numpy first against an explicit target platform/deployment
# target forces the older, broadly-compatible wheel; the project install
# below then leaves it in place since it already satisfies pandas's
# requirement on numpy.
echo "Installing numpy pinned to a macOS 12-compatible wheel"
MACOSX_DEPLOYMENT_TARGET=12.0 uv pip install --python "${VENV_DIR}/bin/python" --python-platform "${NUMPY_TARGET_PLATFORM}" numpy

echo "Installing build dependencies"
"${UV_PIP_RUNNER[@]}" . pyinstaller

echo "Cleaning previous build output"
rm -rf "${BUILD_DIR}" "${DIST_DIR}/${APP_BUNDLE}" "${DMG_PATH}"
mkdir -p "${BUILD_DIR}" "${DIST_DIR}"

echo "Building ${TARGET_ARCH} app bundle"
TARGET_ARCH="${TARGET_ARCH}" APP_VERSION="${VERSION}" "${PYINSTALLER_RUNNER[@]}" --clean --noconfirm "${SPEC_FILE}"

APP_PATH="${DIST_DIR}/${APP_BUNDLE}"
if [[ ! -d "${APP_PATH}" ]]; then
  echo "Expected app bundle not found at ${APP_PATH}" >&2
  exit 1
fi

WARN_FILE="${BUILD_DIR}/run/warn-run.txt"
if [[ -f "${WARN_FILE}" ]] && grep -q "tkinter installation is broken" "${WARN_FILE}"; then
  echo "PyInstaller excluded tkinter from the build (broken interpreter) - the packaged app would crash on launch." >&2
  exit 1
fi

echo "Applying ad-hoc signature"
xattr -cr "${APP_PATH}" || true
codesign --force --deep --sign - "${APP_PATH}"

echo "Preparing DMG staging directory"
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"
cp -R "${APP_PATH}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

echo "Creating DMG at ${DMG_PATH}"
hdiutil create \
  -volname "${DMG_VOLUME_NAME}" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

codesign --force --sign - "${DMG_PATH}" || true

echo "Done"
echo "App: ${APP_PATH}"
echo "DMG: ${DMG_PATH}"
