WITH aware_vmps AS (
  SELECT DISTINCT
    vmp.id AS vmp_id,
    vmp.nm AS vmp_nm,
    vmp.bnf_code AS bnf_code,
    aware.aware_2019,  -- Historic AWaRE categories
    aware.aware_2024 -- Current AWaRE categories
  FROM `{project}.{measures}.tbl__aware_vtms` aware -- Table containing VTM IDs and their AWaRE categories
  INNER JOIN `{project}.{dmd}.vmp` vmp 
    ON aware.vtm_id = vmp.vtm
  INNER JOIN `{project}.{dmd}.ont` ont 
    ON vmp.id = ont.vmp
  INNER JOIN `{project}.{dmd}.ontformroute` ofr 
    ON ont.form = ofr.cd
  WHERE (
    aware.atc_route IS NULL
    OR (
      aware.atc_route = 'P'
      AND SUBSTR(ofr.descr, STRPOS(ofr.descr, '.') + 1) -- Substring to get the route from the ontformroute description
        IN ('intravenous', 'intramuscular', 'intramuscular-deep') -- Where the AWaRe category is defined with a 'P' route match only these dmd forms
    )
    OR (
      aware.atc_route = 'O'
      AND ofr.descr LIKE '%.oral'  -- Where the AWaRe category is defined with a 'O' route match only these dmd forms
    )
  )
  AND SUBSTR(ofr.descr, STRPOS(ofr.descr, '.') + 1)  -- Substring to get the route from the ontformroute description
    IN ('inhalation', 'intramuscular', 'intramuscular-deep', 'intravenous', 'oral', 'vaginal', 'gastroenteral', 'rectal') -- Only include systemic forms that are relevant for AWaRe categorisation
  AND ofr.descr != 'gel.vaginal' -- Exclude 'gel.vaginal' as considered more for localised effect
  AND ofr.descr != 'cream.vaginal' -- Exclude 'cream.vaginal' as considered more for localised effect
)

SELECT
    rx.month AS month, 
    rx.practice AS practice, 
    rx.bnf_name AS bnf_name,
    rx.bnf_code AS bnf_code,
    aware_vmps.aware_2024 AS aware,
    SUM(quantity) AS quantity,
    SUM(items) AS items
FROM 
    {hscic}.normalised_prescribing AS rx
INNER JOIN 
    aware_vmps
    ON CONCAT(SUBSTR(rx.bnf_code, 0, 9), SUBSTR(rx.bnf_code, -2)) = CONCAT(SUBSTR(aware_vmps.bnf_code, 0, 9), SUBSTR(aware_vmps.bnf_code, -2)) --joins "generic" BNF code to dm+d
WHERE 
    aware_vmps.aware_2024 IN ('Access', 'Watch', 'Reserve')
GROUP BY 
    month,
    rx.practice,
    rx.bnf_name, 
    rx.bnf_code, 
    aware_vmps.aware_2024