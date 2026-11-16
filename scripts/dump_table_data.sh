#!/bin/bash
# Dump table data to stdout.
#
# shfmt --indent 4 --write scripts/dump_table_data.sh

set -euo pipefail

echo -n '[sudo] password on largeweb2: ' 1>&2
read -rs password

echo -e '\nDumping table data...' 1>&2

echo "$password" | ssh largeweb2.ebmdatalab.net sudo --stdin --prompt='' -u postgres pg_dump \
    --data-only \
    --table='dmd_*' \
    --table='frontend_chemical' \
    --table='frontend_ncsoconcession' \
    --table='frontend_pcn' \
    --table='frontend_pct' \
    --table='frontend_practice' \
    --table='frontend_presentation' \
    --table='frontend_product' \
    --table='frontend_regionalteam' \
    --table='frontend_section' \
    --table='frontend_stp' \
    --table='frontend_tariffprice' \
    prescribing
