"""A command to generate the SQL required to aggregate statistics
stashed in the JSON column for star_pus in the practice_statistics
table.

When the keys in the JSON change, replace
`views_sql/ccgstatistics.sql` with the output of running this command

"""

from django.core.management import BaseCommand
from django.template import Context, Template


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        keys = [
            "analgesics_cost",
            "antidepressants_adq",
            "antidepressants_cost",
            "antiepileptic_drugs_cost",
            "antiplatelet_drugs_cost",
            "benzodiazepine_caps_and_tabs_cost",
            "bisphosphonates_and_other_drugs_cost",
            "bronchodilators_cost",
            "calcium-channel_blockers_cost",
            "cox-2_inhibitors_cost",
            "drugs_acting_on_benzodiazepine_receptors_cost",
            "drugs_affecting_the_renin_angiotensin_system_cost",
            "drugs_for_dementia_cost",
            "drugs_used_in_parkinsonism_and_related_disorders_cost",
            "hypnotics_adq",
            "inhaled_corticosteroids_cost",
            "laxatives_cost",
            "lipid-regulating_drugs_cost",
            "omega-3_fatty_acid_compounds_adq",
            "oral_antibacterials_cost",
            "oral_antibacterials_item",
            "oral_nsaids_cost",
            "proton_pump_inhibitors_cost",
            "statins_cost",
            "ulcer_healing_drugs_cost",
        ]

        sql = """
-- This SQL is generated by `generate_ccg_statistics_sql.py`

CREATE TEMPORARY FUNCTION
  jsonify_starpu({% for safe_key in safe_keys %}
    {{ safe_key }} FLOAT64{% if not forloop.last %},{% endif %}{% endfor %}
  )
  RETURNS STRING
  LANGUAGE js AS '''
  var obj = {};{% for key, safe_key in zipped_keys %}
  obj['{{ key }}'] = {{ safe_key }};{% endfor %}
  return JSON.stringify(obj);
  ''';

SELECT
  month AS date,
  practices.ccg_id AS pct_id,
  ccgs.name AS name,
  SUM(total_list_size) AS total_list_size,
  SUM(astro_pu_items) AS astro_pu_items,
  SUM(astro_pu_cost) AS astro_pu_cost,
  jsonify_starpu({% for key in keys %}
    SUM(CAST(JSON_EXTRACT_SCALAR(star_pu, '$.{{ key }}') AS FLOAT64)){% if not forloop.last %},{% endif %}{% endfor %}
  ) AS star_pu
FROM {hscic}.practice_statistics
INNER JOIN {hscic}.practices
  ON practice_statistics.practice = practices.code
INNER JOIN {hscic}.ccgs ccgs
  ON practices.ccg_id = ccgs.code AND ccgs.org_type = 'CCG'
WHERE month > TIMESTAMP(DATE_SUB(DATE "{this_month}", INTERVAL 5 YEAR))
GROUP BY
  month,
  practices.ccg_id,
  name
""".strip()

        template = Template(sql)
        safe_keys = [key.replace("-", "_") for key in keys]
        zipped_keys = list(zip(keys, safe_keys))

        ctx = Context(
            {"keys": keys, "safe_keys": safe_keys, "zipped_keys": zipped_keys},
            autoescape=False,
        )
        print(template.render(ctx))
