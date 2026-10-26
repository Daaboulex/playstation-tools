{ runCommand, playstation-tools }:
runCommand "fpkg-playgo-boundary" { nativeBuildInputs = [ playstation-tools ]; } ''
  cp -r --no-preserve=mode ${./playgo-trigger} dump
  truncate -s $((0x10000)) dump/eboot.bin
  truncate -s $((0x7A500)) dump/sce_sys/pic1.png
  mkdir "$out"
  pst fpkg --dir "$out" dump
''
