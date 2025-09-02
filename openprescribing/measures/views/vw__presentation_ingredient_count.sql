-- This view describes the number of separate ingredients in each presentation.  It's useful to have for areas like identifying where inhalers have multiple ingredients.
SELECT
  presentation_code as bnf_code,
  COUNT(ing) AS ing_count
FROM
  dmd.vpi vpi
INNER JOIN
  dmd.vmp vmp
ON
  vmp.id = vpi.vmp
INNER JOIN
  hscic.bnf AS bnf
ON
  CONCAT(SUBSTR(bnf.presentation_code, 0, 9),'AA',SUBSTR(bnf.presentation_code,-2, 2)) = CONCAT(SUBSTR(vmp.bnf_code, 0, 11),SUBSTR(vmp.bnf_code,-2, 2))
WHERE
  presentation_code LIKE '03%'
GROUP BY
  bnf_code
