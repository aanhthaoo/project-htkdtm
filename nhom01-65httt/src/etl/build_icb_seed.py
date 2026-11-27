"""Sinh seed ICB (cấp 1 đến 4) cho dim_sector: src/dbt_dw/seeds/icb.csv.

Cấu trúc ICB 2008 (Industry > Supersector > Sector > Subsector). Nguồn mã: Vietcap iQ cho cấp 2
và cấp 4; cấp 1 và 3 suy ra từ tiền tố. Tên cấp 1 và 2 đã đối chiếu với trường `sector` của Vietcap
(cấp 2). Tên cấp 3 và 4 viết theo trí nhớ về chuẩn ICB 2008 nên đánh dấu name_verified = false,
cần đối chiếu với tài liệu ICB trước khi đưa vào báo cáo.

Chạy:  python src/etl/build_icb_seed.py
"""

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "dbt_dw" / "seeds" / "icb.csv"

# cấp 1: mã -> (tên Anh, tên Việt)
INDUSTRIES = {
    "0001": ("Oil & Gas", "Dầu khí"),
    "1000": ("Basic Materials", "Vật liệu cơ bản"),
    "2000": ("Industrials", "Công nghiệp"),
    "3000": ("Consumer Goods", "Hàng tiêu dùng"),
    "4000": ("Health Care", "Y tế"),
    "5000": ("Consumer Services", "Dịch vụ tiêu dùng"),
    "6000": ("Telecommunications", "Viễn thông"),
    "7000": ("Utilities", "Tiện ích"),
    "8000": ("Financials", "Tài chính"),
    "9000": ("Technology", "Công nghệ"),
}

# cấp 2: mã -> (cấp 1, tên Anh, tên Việt)
SUPERSECTORS = {
    "0500": ("0001", "Oil & Gas", "Dầu khí"),
    "1300": ("1000", "Chemicals", "Hóa chất"),
    "1700": ("1000", "Basic Resources", "Tài nguyên cơ bản"),
    "2300": ("2000", "Construction & Materials", "Xây dựng và vật liệu"),
    "2700": ("2000", "Industrial Goods & Services", "Hàng và dịch vụ công nghiệp"),
    "3300": ("3000", "Automobiles & Parts", "Ô tô và phụ tùng"),
    "3500": ("3000", "Food & Beverage", "Thực phẩm và đồ uống"),
    "3700": ("3000", "Personal & Household Goods", "Hàng cá nhân và gia dụng"),
    "4500": ("4000", "Health Care", "Y tế"),
    "5300": ("5000", "Retail", "Bán lẻ"),
    "5500": ("5000", "Media", "Truyền thông"),
    "5700": ("5000", "Travel & Leisure", "Du lịch và giải trí"),
    "6500": ("6000", "Telecommunications", "Viễn thông"),
    "7500": ("7000", "Utilities", "Điện, nước và khí đốt"),
    "8300": ("8000", "Banks", "Ngân hàng"),
    "8500": ("8000", "Insurance", "Bảo hiểm"),
    "8600": ("8000", "Real Estate", "Bất động sản"),
    "8700": ("8000", "Financial Services", "Dịch vụ tài chính"),
    "9500": ("9000", "Technology", "Công nghệ thông tin"),
}

# cấp 3: mã -> tên Anh (cấp 2 suy ra từ chữ số: tra theo bảng dưới)
SECTORS = {
    "0530": ("0500", "Oil & Gas Producers"),
    "0570": ("0500", "Oil Equipment, Services & Distribution"),
    "0580": ("0500", "Alternative Energy"),
    "1350": ("1300", "Chemicals"),
    "1730": ("1700", "Forestry & Paper"),
    "1750": ("1700", "Industrial Metals & Mining"),
    "1770": ("1700", "Mining"),
    "2350": ("2300", "Construction & Materials"),
    "2710": ("2700", "Aerospace & Defense"),
    "2720": ("2700", "General Industrials"),
    "2730": ("2700", "Electronic & Electrical Equipment"),
    "2750": ("2700", "Industrial Engineering"),
    "2770": ("2700", "Industrial Transportation"),
    "2790": ("2700", "Support Services"),
    "3350": ("3300", "Automobiles & Parts"),
    "3530": ("3500", "Beverages"),
    "3570": ("3500", "Food Producers"),
    "3720": ("3700", "Household Goods & Home Construction"),
    "3740": ("3700", "Leisure Goods"),
    "3760": ("3700", "Personal Goods"),
    "3780": ("3700", "Tobacco"),
    "4530": ("4500", "Health Care Equipment & Services"),
    "4570": ("4500", "Pharmaceuticals & Biotechnology"),
    "5330": ("5300", "Food & Drug Retailers"),
    "5370": ("5300", "General Retailers"),
    "5550": ("5500", "Media"),
    "5750": ("5700", "Travel & Leisure"),
    "6530": ("6500", "Fixed Line Telecommunications"),
    "6570": ("6500", "Mobile Telecommunications"),
    "7530": ("7500", "Electricity"),
    "7570": ("7500", "Gas, Water & Multiutilities"),
    "8350": ("8300", "Banks"),
    "8530": ("8500", "Nonlife Insurance"),
    "8570": ("8500", "Life Insurance"),
    "8630": ("8600", "Real Estate Investment & Services"),
    "8670": ("8600", "Real Estate Investment Trusts"),
    "8770": ("8700", "Financial Services"),
    "8980": ("8700", "Equity Investment Instruments"),
    "8990": ("8700", "Nonequity Investment Instruments"),
    "9530": ("9500", "Software & Computer Services"),
    "9570": ("9500", "Technology Hardware & Equipment"),
}

# cấp 4: mã -> tên Anh (cấp 3 = ba chữ số đầu + "0")
SUBSECTORS = {
    "0533": "Exploration & Production", "0537": "Integrated Oil & Gas",
    "0573": "Oil Equipment & Services", "0577": "Pipelines",
    "0583": "Renewable Energy Equipment", "0587": "Alternative Fuels",
    "1353": "Commodity Chemicals", "1357": "Specialty Chemicals",
    "1733": "Forestry", "1737": "Paper",
    "1753": "Aluminum", "1755": "Nonferrous Metals", "1757": "Iron & Steel",
    "1771": "Coal", "1773": "Diamonds & Gemstones", "1775": "General Mining",
    "1777": "Gold Mining", "1779": "Platinum & Precious Metals",
    "2353": "Building Materials & Fixtures", "2357": "Heavy Construction",
    "2713": "Aerospace", "2717": "Defense",
    "2723": "Containers & Packaging", "2727": "Diversified Industrials",
    "2733": "Electrical Components & Equipment", "2737": "Electronic Equipment",
    "2753": "Commercial Vehicles & Trucks", "2757": "Industrial Machinery",
    "2771": "Delivery Services", "2773": "Marine Transportation", "2775": "Railroads",
    "2777": "Transportation Services", "2779": "Trucking",
    "2791": "Business Support Services", "2793": "Business Training & Employment Agencies",
    "2795": "Financial Administration", "2797": "Industrial Suppliers",
    "2799": "Waste & Disposal Services",
    "3353": "Automobiles", "3355": "Auto Parts", "3357": "Tires",
    "3533": "Brewers", "3535": "Distillers & Vintners", "3537": "Soft Drinks",
    "3573": "Farming & Fishing", "3577": "Food Products",
    "3722": "Durable Household Products", "3724": "Nondurable Household Products",
    "3726": "Furnishings", "3728": "Home Construction",
    "3743": "Consumer Electronics", "3745": "Recreational Products", "3747": "Toys",
    "3763": "Clothing & Accessories", "3765": "Footwear", "3767": "Personal Products",
    "3785": "Tobacco",
    "4533": "Health Care Providers", "4535": "Medical Equipment", "4537": "Medical Supplies",
    "4573": "Biotechnology", "4577": "Pharmaceuticals",
    "5333": "Drug Retailers", "5337": "Food Retailers & Wholesalers",
    "5371": "Apparel Retailers", "5373": "Broadline Retailers",
    "5375": "Home Improvement Retailers", "5377": "Specialty Retailers",
    "5379": "Specialized Consumer Services",
    "5553": "Broadcasting & Entertainment", "5555": "Media Agencies", "5557": "Publishing",
    "5751": "Airlines", "5752": "Gambling", "5753": "Hotels", "5755": "Recreational Services",
    "5757": "Restaurants & Bars", "5759": "Travel & Tourism",
    "6535": "Fixed Line Telecommunications", "6575": "Mobile Telecommunications",
    "7535": "Conventional Electricity", "7537": "Alternative Electricity",
    "7573": "Gas Distribution", "7575": "Multiutilities", "7577": "Water",
    "8355": "Banks",
    "8532": "Full Line Insurance", "8534": "Insurance Brokers",
    "8536": "Property & Casualty Insurance", "8538": "Reinsurance",
    "8575": "Life Insurance",
    "8633": "Real Estate Holding & Development", "8637": "Real Estate Services",
    "8671": "Industrial & Office REITs", "8672": "Retail REITs", "8673": "Residential REITs",
    "8674": "Diversified REITs", "8675": "Specialty REITs", "8676": "Mortgage REITs",
    "8677": "Hotel & Lodging REITs",
    "8771": "Asset Managers", "8773": "Consumer Finance", "8775": "Specialty Finance",
    "8777": "Investment Services", "8779": "Mortgage Finance",
    "8985": "Equity Investment Instruments", "8995": "Nonequity Investment Instruments",
    "9533": "Computer Services", "9535": "Internet", "9537": "Software",
    "9572": "Computer Hardware", "9574": "Electronic Office Equipment",
    "9576": "Semiconductors", "9578": "Telecommunications Equipment",
}  # fmt: skip


def rows() -> list[dict]:
    out = []
    for code, (en, vi) in INDUSTRIES.items():
        out.append(
            dict(
                icb_code=code, level=1, parent_code="", name_en=en, name_vi=vi, name_verified="true"
            )
        )
    for code, (parent, en, vi) in SUPERSECTORS.items():
        out.append(
            dict(
                icb_code=code,
                level=2,
                parent_code=parent,
                name_en=en,
                name_vi=vi,
                name_verified="true",
            )
        )
    for code, (parent, en) in SECTORS.items():
        out.append(
            dict(
                icb_code=code,
                level=3,
                parent_code=parent,
                name_en=en,
                name_vi="",
                name_verified="false",
            )
        )
    for code, en in SUBSECTORS.items():
        parent = code[:3] + "0"
        assert parent in SECTORS, f"cấp 4 {code} không có cấp 3 {parent}"
        out.append(
            dict(
                icb_code=code,
                level=4,
                parent_code=parent,
                name_en=en,
                name_vi="",
                name_verified="false",
            )
        )
    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = rows()
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["icb_code", "level", "parent_code", "name_en", "name_vi", "name_verified"],
        )
        writer.writeheader()
        writer.writerows(data)
    print(f"Đã ghi {len(data)} dòng vào {OUT}")


if __name__ == "__main__":
    main()
