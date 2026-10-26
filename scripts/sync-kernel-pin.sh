if [ ! -f kernel.json ]; then
  echo "run this from the playstation-tools root: kernel.json is not in $(pwd)" >&2
  exit 1
fi

release=$PATCH_SET_KERNEL
case "$release" in
*.*.0) release=${release%.0} ;;
esac

if jq -e --arg release "$release" 'has($release)' kernel.json >/dev/null; then
  echo "kernel.json already holds the hash of linux $release, the kernel the PS5 patch set targets"
  exit 0
fi

url="https://cdn.kernel.org/pub/linux/kernel/v${release%%.*}.x/linux-${release}.tar.xz"
tarball=$(mktemp)
trap 'rm -f "$tarball"' EXIT
curl -fsSL --retry 5 --retry-all-errors "$url" -o "$tarball"
digest=$(openssl dgst -sha256 -binary "$tarball" | base64 -w0)
if [ ${#digest} -ne 44 ]; then
  echo "could not hash $url: got '$digest'" >&2
  exit 1
fi

jq -n --arg release "$release" --arg hash "sha256-$digest" '{($release): $hash}' >kernel.json.new
mv kernel.json.new kernel.json
echo "kernel.json now holds the hash of linux $release, from $url"
