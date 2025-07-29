WITH matched_vtms AS ( -- This query does the fuzzy matching of Antibiotic name to VTM name
  SELECT  
    aware.Antibiotic,
    aware.atc_route,
    aware.aware_2019,
    aware.aware_2024,
    vtm.nm,
    vtm.id,
    CASE
      WHEN aware.Antibiotic = vtm.nm THEN 'DIRECT'
      ELSE 'ASSUMED'
    END AS match_type
  FROM measures.aware_grouping
  LEFT JOIN {project}.{dmd}.vtm vtm 
    ON vtm.nm LIKE CONCAT('%', aware.Antibiotic, '%')
  WHERE vtm.invalid IS NOT TRUE
),

duplicate_vtms AS ( -- This produces a list of duplicate rows where a direct match already exists
  SELECT *
  FROM matched_vtms
  WHERE nm IN (
    SELECT nm
    FROM matched_vtms
    WHERE atc_route IS NULL
    GROUP BY nm
    HAVING COUNT(*) > 1
  )
  AND match_type = 'ASSUMED'
),

vmp_with_route AS (
  SELECT DISTINCT
    vmp.id AS id,
    vmp.bnf_code AS bnf_code,
    vmp.vtm AS vtm,
    vmp.nm AS nm,
    COALESCE(sroute.route, routelookup.who_route) AS vmp_atc_route
  FROM {project}.{dmd}.vmp vmp
  LEFT JOIN {project}.{dmd}.ont ont ON vmp.id = ont.vmp
  LEFT JOIN {project}.{dmd}.ontformroute ofr ON ont.form = ofr.cd
  LEFT JOIN measures.vmp_single_route_identifier sroute ON vmp.id = sroute.vmp_id
  LEFT JOIN measures.vw__dmd_to_atc_route routelookup ON ofr.descr = routelookup.dmd_ofr
  WHERE ofr.descr NOT LIKE '%.auricular'
  AND ofr.descr NOT LIKE '%.cutaneous'
  AND ofr.descr NOT LIKE '%.ophthalmic'
  AND ofr.descr NOT LIKE '%.oromucosal'
  AND ofr.descr NOT LIKE '%.intralesional'
  AND ofr.descr NOT LIKE '%.nasal'
  AND ofr.descr NOT LIKE '%.gingival'
  AND ofr.descr != 'gel.vaginal'
  AND ofr.descr != 'cream.vaginal'
),

matched_vmps AS (
  SELECT DISTINCT
    matched_vtms.Antibiotic,
    matched_vtms.nm as vtm_nm,
    matched_vtms.id as vtm_id,
    vmp.nm as vmp_nm,
    vmp.id as vmp_id,
    vmp.vmp_atc_route,
    matched_vtms.atc_route,
    matched_vtms.aware_2019,
    matched_vtms.aware_2024
  FROM matched_vtms
  LEFT JOIN vmp_with_route vmp
    ON matched_vtms.id = vmp.vtm
    AND (
      matched_vtms.atc_route IS NULL
      OR matched_vtms.atc_route = vmp.vmp_atc_route
    )
  WHERE NOT EXISTS ( -- removes the duplicates identified above
    SELECT 1
    FROM duplicate_vtms
    WHERE matched_vtms.Antibiotic = duplicate_vtms.Antibiotic AND matched_vtms.nm = duplicate_vtms.nm
  ) AND vmp.id IS NOT NULL
  ORDER BY matched_vtms.Antibiotic ASC;
)

SELECT
    rx.month AS month, 
    rx.practice AS practice, 
    rx.bnf_name AS bnf_name,
    rx.bnf_code AS bnf_code,
    aware.aware_2024 AS aware,
    SUM(quantity) AS quantity,
    SUM(items) AS items
FROM 
    {project}.{hscic}.normalised_prescribing AS rx
INNER JOIN 
    {project}.{dmd}.vmp AS vmp
    ON CONCAT(SUBSTR(rx.bnf_code, 0, 9), SUBSTR(rx.bnf_code, -2)) = CONCAT(SUBSTR(vmp.bnf_code, 0, 9), SUBSTR(vmp.bnf_code, -2)) --joins "generic" BNF code to dm+d
INNER JOIN 
    matched_vmps AS aware
    ON SUBSTR(rx.bnf_code, 0, 9) = SUBSTR(matched_vmps.bnf_code, 0, 9)
WHERE 
    aware.aware_2024 IN ('Access', 'Watch', 'Reserve')
GROUP BY 
    month,
    rx.practice,
    rx.bnf_name, 
    rx.bnf_code, 
    aware.aware_2024