CUSTOMER_TYPE_MAP = {
    "Individual-Residential":     "HOME",
    "Individual-Business":        "HOME",
    "Religious Institute":        "HOME",
    "Government Organization":    "ENTERPRISE",
    "SLT-Office":                 "ENTERPRISE",
    "Diplomats & Delegates":      "HOME",
    "PayPhone Operator":          "ENTERPRISE",
    "SLT-Call Box":               "ENTERPRISE",
    "SLT-Official Residential":   "HOME",
    "Wholesale-Operator":         "ENTERPRISE",
    "Enterprise-Large":           "ENTERPRISE",
    "Enterprise-Medium":          "ENTERPRISE",
    "Wholesale-ReSeller":         "ENTERPRISE",
    "Corporate-Global":           "ENTERPRISE",
    "Association":                "HOME",
    "NGO":                        "HOME",
    "Govt.-Official Residential": "HOME",
    "SLT-Group":                  "ENTERPRISE",
    "Regional-SME":               "ENTERPRISE",
    "Small Business":             "ENTERPRISE",
    "International Operator":     "ENTERPRISE",
    "International Business":     "ENTERPRISE",
    "Small Biz without BRN":      "HOME",
    "Individual-Micro Biz":       "ENTERPRISE",
    "Registered-Micro Biz":       "ENTERPRISE",
}


def get_badge(customer_type: str) -> str:
    if not customer_type:
        return "UNKNOWN"
    return CUSTOMER_TYPE_MAP.get(customer_type.strip(), "UNKNOWN")


def is_vat_registered(customer_vat_ref: str) -> bool:
    if not customer_vat_ref:
        return False
    return not customer_vat_ref.strip().upper().startswith("VATDL")


def is_svat_registered(raw_tags: dict) -> bool:
    return bool((raw_tags or {}).get("CUST_SVAT_NUMBER", "").strip())