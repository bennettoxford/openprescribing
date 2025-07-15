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
  FROM `ebmdatalab.chris.aware_list_extended` aware
  LEFT JOIN `ebmdatalab.dmd.vtm` vtm 
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
    vmp.vtm AS vtm,
    vmp.nm AS nm,
    COALESCE(sroute.route, routelookup.who_route) AS vmp_atc_route
  FROM `ebmdatalab.dmd.vmp` vmp
  LEFT JOIN dmd.ont ont ON vmp.id = ont.vmp
  LEFT JOIN dmd.ontformroute ofr ON ont.form = ofr.cd
  LEFT JOIN chris.vmp_single_route_identifier sroute ON vmp.id = sroute.vmp_id
  LEFT JOIN `scmd_dmd_views.dmd_to_atc_route` routelookup ON ofr.descr = routelookup.dmd_ofr
  WHERE ofr.descr NOT LIKE '%.auricular'
  AND ofr.descr NOT LIKE '%.cutaneous'
  AND ofr.descr NOT LIKE '%.ophthalmic'
  AND ofr.descr NOT LIKE '%.oromucosal'
  AND ofr.descr NOT LIKE '%.intralesional'
  AND ofr.descr NOT LIKE '%.nasal'
  AND ofr.descr NOT LIKE '%.gingival'
  AND ofr.descr != 'gel.vaginal'
  AND ofr.descr != 'cream.vaginal'
)

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