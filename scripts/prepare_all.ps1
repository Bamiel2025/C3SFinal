# Préparation complète des données C3S² (lancée en arrière-plan).
#   powershell -File scripts/prepare_all.ps1
# Les journaux sont écrits dans data/prep_*.log.

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -X utf8 scripts/prepare_data.py cities 2>&1 | Tee-Object -FilePath data/prep_cities.log
python -X utf8 scripts/prepare_maps.py        2>&1 | Tee-Object -FilePath data/prep_maps.log
python -X utf8 scripts/prepare_data.py heat   2>&1 | Tee-Object -FilePath data/prep_heat.log

"TERMINE $(Get-Date -Format HH:mm:ss)" | Tee-Object -FilePath data/prep_done.log
