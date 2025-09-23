from gcutils.bigquery import build_schema

DMD_SCHEMA = build_schema(
    ("dmdid", "STRING"),
    ("bnf_code", "STRING"),
    ("vpid", "STRING"),
    ("display_name", "STRING"),
    ("ema", "STRING"),
    ("pres_statcd", "STRING"),
    ("avail_restrictcd", "STRING"),
    ("product_type", "STRING"),
    ("non_availcd", "STRING"),
    ("concept_class", "STRING"),
    ("nurse_f", "STRING"),
    ("dent_f", "STRING"),
    ("prod_order_no", "STRING"),
    ("sched_1", "STRING"),
    ("sched_2", "STRING"),
    ("padm", "STRING"),
    ("fp10_mda", "STRING"),
    ("acbs", "STRING"),
    ("assort_flav", "STRING"),
    ("catcd", "STRING"),
    ("tariff_category", "STRING"),
    ("flag_imported", "STRING"),
    ("flag_broken_bulk", "STRING"),
    ("flag_non_bioequivalence", "STRING"),
    ("flag_special_containers", "BOOLEAN"),
)

CCG_SCHEMA = build_schema(
    ("code", "STRING"),
    ("name", "STRING"),
    ("ons_code", "STRING"),
    ("org_type", "STRING"),
    ("open_date", "TIMESTAMP"),
    ("close_date", "TIMESTAMP"),
    ("address", "STRING"),
    ("postcode", "STRING"),
    ("stp_id", "STRING"),
    ("regional_team_id", "STRING"),
)

PRESCRIBING_SCHEMA = build_schema(
    ("sha", "STRING"),
    ("pct", "STRING"),
    ("practice", "STRING"),
    ("bnf_code", "STRING"),
    ("bnf_name", "STRING"),
    ("items", "INTEGER"),
    ("net_cost", "FLOAT"),
    ("actual_cost", "FLOAT"),
    ("quantity", "FLOAT"),
    ("month", "TIMESTAMP"),
)

PRESENTATION_SCHEMA = build_schema(
    ("bnf_code", "STRING"),
    ("name", "STRING"),
    ("is_generic", "BOOLEAN"),
    ("adq_per_quantity", "FLOAT"),
)

PRACTICE_SCHEMA = build_schema(
    ("code", "STRING"),
    ("name", "STRING"),
    ("address1", "STRING"),
    ("address2", "STRING"),
    ("address3", "STRING"),
    ("address4", "STRING"),
    ("address5", "STRING"),
    ("postcode", "STRING"),
    ("location", "STRING"),
    ("ccg_id", "STRING"),
    ("pcn_id", "STRING"),
    ("setting", "INTEGER"),
    ("close_date", "STRING"),
    ("join_provider_date", "STRING"),
    ("leave_provider_date", "STRING"),
    ("open_date", "STRING"),
    ("status_code", "STRING"),
)

PRACTICE_STATISTICS_SCHEMA = build_schema(
    ("month", "TIMESTAMP"),
    ("male_0_4", "INTEGER"),
    ("female_0_4", "INTEGER"),
    ("male_5_14", "INTEGER"),
    ("male_15_24", "INTEGER"),
    ("male_25_34", "INTEGER"),
    ("male_35_44", "INTEGER"),
    ("male_45_54", "INTEGER"),
    ("male_55_64", "INTEGER"),
    ("male_65_74", "INTEGER"),
    ("male_75_plus", "INTEGER"),
    ("female_5_14", "INTEGER"),
    ("female_15_24", "INTEGER"),
    ("female_25_34", "INTEGER"),
    ("female_35_44", "INTEGER"),
    ("female_45_54", "INTEGER"),
    ("female_55_64", "INTEGER"),
    ("female_65_74", "INTEGER"),
    ("female_75_plus", "INTEGER"),
    ("total_list_size", "INTEGER"),
    ("astro_pu_cost", "FLOAT"),
    ("astro_pu_items", "FLOAT"),
    ("star_pu", "STRING"),
    ("pct_id", "STRING"),
    ("practice", "STRING"),
)

TARIFF_SCHEMA = build_schema(
    ("bnf_name", "STRING"),
    ("bnf_code", "STRING"),
    ("category", "STRING"),
    ("date", "DATE"),
)

BNF_SCHEMA = build_schema(
    ("year_month", "STRING"),
    ("chapter", "STRING"),
    ("chapter_code", "STRING"),
    ("section", "STRING"),
    ("section_code", "STRING"),
    ("para", "STRING"),
    ("para_code", "STRING"),
    ("subpara", "STRING"),
    ("subpara_code", "STRING"),
    ("chemical", "STRING"),
    ("chemical_code", "STRING"),
    ("product", "STRING"),
    ("product_code", "STRING"),
    ("presentation", "STRING"),
    ("presentation_code", "STRING"),
)

RAW_PRESCRIBING_SCHEMA_V1 = build_schema(
    ("Regional_Office_Name", "STRING"),
    ("Regional_Office_Code", "STRING"),
    ("Area_Team_Name", "STRING"),
    ("Area_Team_Code", "STRING"),
    ("PCO_Name", "STRING"),
    ("PCO_Code", "STRING"),
    ("Practice_Name", "STRING"),
    ("Practice_Code", "STRING"),
    ("BNF_Code", "STRING"),
    ("BNF_Description", "STRING"),
    ("Items", "INTEGER"),
    ("Quantity", "INTEGER"),
    ("ADQ_Usage", "FLOAT"),
    ("NIC", "FLOAT"),
    ("Actual_Cost", "FLOAT"),
)

RAW_PRESCRIBING_SCHEMA_V2 = build_schema(
    ("YEAR_MONTH", "STRING"),
    ("REGIONAL_OFFICE_NAME", "STRING"),
    ("REGIONAL_OFFICE_CODE", "STRING"),
    ("ICB_NAME", "STRING"),
    ("ICB_CODE", "STRING"),
    ("PCO_NAME", "STRING"),
    ("PCO_CODE", "STRING"),
    ("PRACTICE_NAME", "STRING"),
    ("PRACTICE_CODE", "STRING"),
    ("ADDRESS_1", "STRING"),
    ("ADDRESS_2", "STRING"),
    ("ADDRESS_3", "STRING"),
    ("ADDRESS_4", "STRING"),
    ("POSTCODE", "STRING"),
    ("BNF_CHEMICAL_SUBSTANCE_CODE", "STRING"),
    ("BNF_CHEMICAL_SUBSTANCE_NAME", "STRING"),
    ("BNF_PRESENTATION_CODE", "STRING"),
    ("BNF_PRESENTATION_NAME", "STRING"),
    ("BNF_CHAPTER_PLUS_CODE", "STRING"),
    ("QUANTITY", "FLOAT"),
    ("ITEMS", "INTEGER"),
    ("TOTAL_QUANTITY", "FLOAT"),
    ("ADQ_USAGE", "FLOAT"),
    ("NIC", "FLOAT"),
    ("ACTUAL_COST", "FLOAT"),
    ("UNIDENTIFIED", "STRING"),
    ("SNOMED_CODE", "STRING"),
)

BDZ_ADQ_SCHEMA = build_schema(
    ("bnf_code", "STRING"),
    ("name", "STRING"),
    ("is_generic", "BOOLEAN"),
    ("active_quantity", "FLOAT"),
    ("adq", "FLOAT"),
    ("adq_unit", "STRING"),
    ("percent_of_adq", "FLOAT"),
)

BNF_MAP_SCHEMA = build_schema(
    ("former_bnf_code", "STRING"), ("current_bnf_code", "STRING")
)

PCN_SCHEMA = build_schema(("code", "STRING"), ("name", "STRING"))

STP_SCHEMA = build_schema(("code", "STRING"), ("name", "STRING"))

REGIONAL_TEAM_SCHEMA = build_schema(
    ("code", "STRING"),
    ("name", "STRING"),
    ("open_date", "DATE"),
    ("close_date", "DATE"),
)


def statistics_transform(row):
    """Transform a row from the frontend_practicestatistics table so it
    matches our statistics schema

    """
    row[0] = "%s 00:00:00" % row[0]  # BQ TIMESTAMP format
    return row


def presentation_transform(row):
    """Transform a row from the frontend_presentation table so it
    matches our statistics schema

    """
    if row[2] == "t":
        row[2] = "true"
    else:
        row[2] = "false"
    return row


def ccgs_transform(row):
    if row[4]:
        row[4] = "%s 00:00:00" % row[4]
    if row[5]:
        row[5] = "%s 00:00:00" % row[5]
    return row
