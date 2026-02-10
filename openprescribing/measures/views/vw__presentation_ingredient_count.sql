-- This view describes the number of separate ingredients in each presentation.  It's useful to have for areas like identifying where inhalers have multiple ingredients.
SELECT
  vmp,
  presentation_code as bnf_code,
  COUNT(ing) AS ing_count
FROM
  {project}.dmd.vpi AS vpi
INNER JOIN
  {project}.dmd.vmp AS v
ON
  v.id = vpi.vmp
INNER JOIN
  {project}.hscic.bnf AS bnf
ON
  CONCAT(SUBSTR(bnf.presentation_code, 0, 9),'AA',SUBSTR(bnf.presentation_code,-2, 2)) = CONCAT(SUBSTR(v.bnf_code, 0, 11),SUBSTR(v.bnf_code,-2, 2))
GROUP BY
  vmp,
  bnf_code
