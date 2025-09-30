 -- this code creates distinct BNF codes for antibiotics for the AwArE measure

SELECT DISTINCT
  bnf.presentation_code as bnf_code,
  aware.aware_2024 as aware
  FROM ebmdatalab.measures.tbl__aware_vtms aware -- Table containing VTM IDs and their AWaRE categories
  INNER JOIN ebmdatalab.dmd.vmp vmp 
    ON aware.vtm_id = vmp.vtm
  INNER JOIN ebmdatalab.dmd.ont ont 
    ON vmp.id = ont.vmp
  INNER JOIN ebmdatalab.dmd.ontformroute ofr 
    ON ont.form = ofr.cd
  INNER JOIN 
    hscic.bnf bnf
    ON CONCAT(SUBSTR(bnf.presentation_code, 0, 9), SUBSTR(bnf.presentation_code, -2)) = CONCAT(SUBSTR(vmp.bnf_code, 0, 9), SUBSTR(vmp.bnf_code, -2)) --joins "generic" BNF code to dm+d
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
