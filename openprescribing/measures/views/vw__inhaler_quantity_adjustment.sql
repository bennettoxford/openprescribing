-- this view adjusts inhaler quantities where they are showing as doses, rather than inhalers.  If the quantity per item is more than 9, it adjusts by the smallest dm+d pack size.
SELECT
  TIMESTAMP(month) as date,
  rx.bnf_code,
  form.form_route AS form_route,
  CASE
    WHEN IEEE_DIVIDE(SUM(quantity), SUM(items)) >9 THEN MIN(vmpp.qtyval)
    ELSE 1
END
  AS qtyadj
FROM
  hscic.normalised_prescribing AS rx
INNER JOIN
  {project}.dmd.vmpp_full AS vmpp
ON
  CONCAT( SUBSTR(rx.bnf_code, 0, 9), 'AA', SUBSTR(rx.bnf_code,-2, 2) ) = CONCAT( SUBSTR(vmpp.bnf_code, 0, 11), SUBSTR(vmpp.bnf_code,-2, 2) )
INNER JOIN
  {project}.measures.vw__dmd_objs_with_form_route AS form
ON
  form.vpid = vmpp.vmp
WHERE
  form.form_route IN (
    'pressurizedinhalation.inhalation',
    'powderinhalation.inhalation',
    'inhalationsolution.inhalation')
GROUP BY month, rx.bnf_code, form_route
