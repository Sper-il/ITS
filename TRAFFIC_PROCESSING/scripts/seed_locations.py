"""
scripts/seed_locations.py
Seeds the SQLite locations database from HCM_PRESETS + extended HCMC locations.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.data.locations_db import (
    init_db,
    upsert_district,
    add_location,
    get_location_count,
    get_district_count,
)

# ---------------------------------------------------------------------------
# Extended HCMC location data
# ---------------------------------------------------------------------------
# Each entry: (name, lat, lon, district_slug, category)
# district_slug None means "Khác"
HCMC_LOCATIONS: list[tuple[str, float, float, str | None, str]] = [

    # ---- Metro Line 1 stations --------------------------------------------
    ("Ga Bến Thành", 10.7729, 106.6978, "quan-1", "metro"),
    ("Ga Nhà hát TP", 10.7757, 106.7031, "quan-1", "metro"),
    ("Ga Ba Son", 10.7711, 106.7081, "quan-1", "metro"),
    ("Ga Công viên Văn Thánh", 10.7825, 106.7118, "binh-thanh", "metro"),
    ("Ga Tân Cảng", 10.7891, 106.7185, "binh-thanh", "metro"),
    ("Ga Thủ Thiêm", 10.7958, 106.7279, "thu-duc", "metro"),
    ("Ga An Phú", 10.8005, 106.7357, "thu-duc", "metro"),
    ("Ga Bình An", 10.8069, 106.7423, "thu-duc", "metro"),
    ("Ga Thảo Điền", 10.8113, 106.7487, "thu-duc", "metro"),
    ("Ga An Khánh", 10.8185, 106.7551, "thu-duc", "metro"),
    ("Ga Bến xe Miền Đông 2", 10.8267, 106.7602, "thu-duc", "metro"),
    ("Ga Phước Long", 10.8362, 106.7655, "thu-duc", "metro"),
    ("Ga Bác Ái", 10.8460, 106.7698, "thu-duc", "metro"),
    ("Ga Quốc phòng", 10.8555, 106.7732, "thu-duc", "metro"),
    ("Ga Thủ Đức", 10.8658, 106.7771, "thu-duc", "metro"),
    ("Ga Sóng Hồng", 10.8751, 106.7815, "thu-duc", "metro"),
    ("Ga Bến xe Miền Đông", 10.8387, 106.7553, "thu-duc", "metro"),
    ("Ga Bình Thái", 10.8455, 106.7608, "thu-duc", "metro"),
    ("Ga ĐH SPKT", 10.8725, 106.7575, "thu-duc", "metro"),
    ("Ga Phú Hữu", 10.8842, 106.7655, "thu-duc", "metro"),
    ("Ga Rạch Chiếc", 10.8921, 106.7732, "thu-duc", "metro"),
    ("Ga Phú Mỹ Hưng", 10.7298, 106.7160, "quan-7", "metro"),
    ("Ga Cây Khô", 10.7225, 106.7012, "quan-8", "metro"),
    ("Ga Bến Mễ Cốc", 10.7185, 106.6915, "quan-8", "metro"),

    # ---- Quận 1 (additional) -----------------------------------------------
    ("Thủ Thiêm Park", 10.7955, 106.7285, "quan-1", "park"),
    ("Saigon Tax Center", 10.7720, 106.7045, "quan-1", "landmark"),
    ("Union Square", 10.7780, 106.7000, "quan-1", "mall"),
    ("The Marq", 10.7772, 106.7010, "quan-1", "landmark"),
    ("Hotel Majestic", 10.7745, 106.7040, "quan-1", "landmark"),
    ("Caravelle Hotel", 10.7755, 106.7020, "quan-1", "landmark"),
    ("Rex Hotel", 10.7765, 106.7015, "quan-1", "landmark"),
    ("Saigon Notre-Dame", 10.7795, 106.6975, "quan-1", "landmark"),
    ("Bưu điện TP.HCM", 10.7798, 106.6990, "quan-1", "landmark"),
    ("Cầu Thị Nghè", 10.7895, 106.7125, "quan-1", "landmark"),
    ("Hồ Con Rùa", 10.7833, 106.6960, "quan-1", "park"),
    ("Vườn Bách Thảo", 10.7845, 106.6985, "quan-1", "park"),
    ("Cầu Bông", 10.7890, 106.6850, "quan-1", "landmark"),
    ("Cầu Kiệu", 10.7875, 106.6800, "quan-1", "landmark"),

    # ---- Quận 3 (additional) ---------------------------------------------
    ("Voodoo Club", 10.7792, 106.6845, "quan-3", "landmark"),
    ("Trường ĐH Mỹ Thuật", 10.7790, 106.6860, "quan-3", "university"),
    ("Trường ĐH Tài Chính Marketing", 10.7835, 106.6810, "quan-3", "university"),
    ("Trường ĐH Văn Hóa", 10.7775, 106.6840, "quan-3", "university"),
    ("Trường ĐH Tự Nhiên", 10.7630, 106.6823, "quan-3", "university"),
    ("Trường ĐH Kiến Trúc", 10.7755, 106.6800, "quan-3", "university"),
    ("Trường ĐH Ngôte", 10.7825, 106.6780, "quan-3", "university"),
    ("Công viên Gia Định", 10.7830, 106.6750, "quan-3", "park"),
    ("Cầu Nguyễn Trãi", 10.7820, 106.6650, "quan-3", "landmark"),
    ("Sân vận động Thống Nhất", 10.7828, 106.6745, "quan-3", "sports"),

    # ---- Quận 4 (additional) ---------------------------------------------
    ("Cầu Ông Lãnh", 10.7645, 106.7020, "quan-4", "landmark"),
    ("Cầu Calmette", 10.7685, 106.7000, "quan-4", "landmark"),
    ("Chợ Xóm Hới", 10.7595, 106.7030, "quan-4", "market"),
    ("Khu tài chính Quận 4", 10.7680, 106.7040, "quan-4", "landmark"),
    ("Tòa nhà REE Tower", 10.7695, 106.7055, "quan-4", "landmark"),
    ("Vinhomes Royal City", 10.7615, 106.7010, "quan-4", "landmark"),

    # ---- Quận 5 (additional) ---------------------------------------------
    ("Chợ Kim Biên", 10.7510, 106.6420, "quan-5", "market"),
    ("Chợ Nhị Yên", 10.7500, 106.6400, "quan-5", "market"),
    ("Bệnh viện Chợ Rẫy", 10.7875, 106.6863, "quan-5", "hospital"),
    ("Trường ĐH Phạm Ngọc Thạch", 10.7645, 106.6730, "quan-5", "university"),
    ("Trường ĐH Y khoa Phạm Ngọc Thạch", 10.7645, 106.6730, "quan-5", "university"),
    ("Cầu Chà Và", 10.7520, 106.6450, "quan-5", "landmark"),
    ("Cầu Bình Đông", 10.7500, 106.6550, "quan-5", "landmark"),
    ("Hồ Xá Tế", 10.7530, 106.6500, "quan-5", "landmark"),

    # ---- Quận 6 (additional) ---------------------------------------------
    ("Cầu Bến Nghé", 10.7470, 106.6580, "quan-6", "landmark"),
    ("Bệnh viện Quân Y 175", 10.8025, 106.6635, "quan-6", "hospital"),
    ("Chợ Lò Rèn", 10.7450, 106.6530, "quan-6", "market"),
    ("Khu Du lịch Hướng Dương", 10.7410, 106.6440, "quan-6", "landmark"),
    ("Trường ĐH Kỹ thuật Y tế", 10.7430, 106.6490, "quan-6", "university"),

    # ---- Quận 7 (additional) ---------------------------------------------
    ("SC Crescent Mall", 10.7285, 106.7230, "quan-7", "mall"),
    ("SC SC VivoCity", 10.7351, 106.7338, "quan-7", "mall"),
    ("SC Paragon", 10.7298, 106.7243, "quan-7", "mall"),
    ("SC Zen Plaza", 10.7315, 106.7250, "quan-7", "mall"),
    ("SC Moonlight Park View", 10.7300, 106.7200, "quan-7", "landmark"),
    ("Bệnh viện Pháp Việt (FV)", 10.7298, 106.7220, "quan-7", "hospital"),
    ("Bệnh viện Tim Tâm Đức", 10.7310, 106.7190, "quan-7", "hospital"),
    ("Đại học Tôn Đức Thắng", 10.7786, 106.6850, "quan-7", "university"),
    ("Rạch Bần", 10.7260, 106.7130, "quan-7", "landmark"),
    ("Cầu Phú Mỹ", 10.7320, 106.7110, "quan-7", "landmark"),
    ("Khu phố Tân Mỹ", 10.7270, 106.7180, "quan-7", "landmark"),
    ("Trung tâm Hội chợ Sài Gòn", 10.7340, 106.7280, "quan-7", "landmark"),
    ("Cầu Thủ Thiêm 1", 10.7940, 106.7240, "quan-7", "landmark"),
    ("Cầu Thủ Thiêm 2", 10.7680, 106.7070, "quan-7", "landmark"),
    ("Khu đô thị Phú Mỹ Hưng", 10.7298, 106.7160, "quan-7", "landmark"),
    ("Sân Golf Rạch Chiếc", 10.8870, 106.7990, "quan-7", "sports"),
    ("Bến du thuyền Phú Mỹ Hưng", 10.7275, 106.7145, "quan-7", "landmark"),
    ("Trường Quốc tế Úc", 10.7305, 106.7175, "quan-7", "school"),
    ("Trường Quốc tế Hàn Quốc", 10.7318, 106.7225, "quan-7", "school"),
    ("Trường Quốc tế Nhật Bản", 10.7290, 106.7200, "quan-7", "school"),
    ("Sàn Giao dịch Chứng khoán", 10.7945, 106.7230, "quan-7", "landmark"),

    # ---- Quận 8 (additional) ---------------------------------------------
    ("Cầu Chữ Y", 10.7455, 106.6835, "quan-8", "landmark"),
    ("Cầu Bến Mớm", 10.7500, 106.6800, "quan-8", "landmark"),
    ("Chợ Bình Đông", 10.7480, 106.6820, "quan-8", "market"),
    ("Khu đô thị mới Bến Nghé", 10.7520, 106.6850, "quan-8", "landmark"),
    ("Cầu Phú Định", 10.7550, 106.6840, "quan-8", "landmark"),
    ("Trường ĐH Công nghệ thực phẩm", 10.7370, 106.6880, "quan-8", "university"),
    ("Trường ĐH Mở TP.HCM", 10.7355, 106.6860, "quan-8", "university"),
    ("Trường ĐH Cửu Long", 10.7420, 106.6850, "quan-8", "university"),
    ("Bệnh viện Bình Điền", 10.7430, 106.6810, "quan-8", "hospital"),

    # ---- Quận 9 / Thủ Đức (additional) ----------------------------------
    ("ĐHQG TP.HCM - ĐH Bách Khoa", 10.8783, 106.8053, "thu-duc", "university"),
    ("ĐHQG TP.HCM - Ký túc xá", 10.8795, 106.8100, "thu-duc", "landmark"),
    ("Khu Công nghệ Cao TP.HCM", 10.8408, 106.8315, "thu-duc", "landmark"),
    ("Trường ĐH Nhân bản quốc tế", 10.8420, 106.8360, "thu-duc", "university"),
    ("Trường ĐH Fulbright Việt Nam", 10.8740, 106.7980, "thu-duc", "university"),
    ("Trường ĐH Kiến Quốc", 10.8800, 106.8120, "thu-duc", "university"),
    ("Trung tâm Thể dục Thể thao Rạch Chiếc", 10.8880, 106.7820, "thu-duc", "sports"),
    ("Sân Golf Đại Phong", 10.8820, 106.7950, "thu-duc", "sports"),
    ("Khu Du lịch Bửu Long", 10.8680, 106.8210, "thu-duc", "landmark"),
    ("Thảo Cầm Viên Sài Gòn", 10.7870, 106.6990, "thu-duc", "landmark"),
    ("Đền thờ Bến Dược", 10.8750, 106.8050, "thu-duc", "landmark"),
    ("Trung tâm Văn hóa Điện ảnh", 10.8720, 106.8090, "thu-duc", "landmark"),
    ("Khu Công nghiệp Long Bình", 10.8510, 106.8120, "thu-duc", "landmark"),
    ("Khu Công nghiệp Amata", 10.8430, 106.8180, "thu-duc", "landmark"),
    ("Khu Công nghiệp Sóng Hồng", 10.8750, 106.7800, "thu-duc", "landmark"),

    # ---- Quận 10 (additional) --------------------------------------------
    ("Cầu Nguyễn Tri Phương", 10.7710, 106.6730, "quan-10", "landmark"),
    ("Bệnh viện Bình Dân", 10.7715, 106.6755, "quan-10", "hospital"),
    ("Trường ĐH Sư phạm Âm nhạc", 10.7700, 106.6770, "quan-10", "university"),
    ("Chợ Sáng Tây", 10.7685, 106.6715, "quan-10", "market"),
    ("Cầu Láng", 10.7715, 106.6650, "quan-10", "landmark"),
    ("Văn miếu Sài Gòn", 10.7835, 106.6980, "quan-10", "landmark"),

    # ---- Quận 11 (additional) --------------------------------------------
    ("Cầu Nhị Thiên Đường", 10.7635, 106.6430, "quan-11", "landmark"),
    ("Cầu Đôi", 10.7620, 106.6460, "quan-11", "landmark"),
    ("Chợ Hòa Bình", 10.7625, 106.6410, "quan-11", "market"),
    ("Bệnh viện Bệnh Nhiệt đới", 10.7640, 106.6560, "quan-11", "hospital"),
    ("Trường ĐH Văn hóa Nghệ thuật", 10.7635, 106.6540, "quan-11", "university"),
    ("Trường Cao đẳng Kinh tế", 10.7645, 106.6580, "quan-11", "university"),

    # ---- Quận 12 (additional) --------------------------------------------
    ("ĐH Sài Gòn - Khoa Y", 10.8555, 106.6500, "quan-12", "university"),
    ("ĐH Tài nguyên Môi trường", 10.8590, 106.6520, "quan-12", "university"),
    ("ĐH Luật Kinh tế", 10.8570, 106.6510, "quan-12", "university"),
    ("Bệnh viện Y học Cổ truyền", 10.8580, 106.6475, "quan-12", "hospital"),
    ("Khu công nghiệp Tân Bửu", 10.8620, 106.6580, "quan-12", "landmark"),
    ("Chợ Tân Hưng Thuận", 10.8600, 106.6540, "quan-12", "market"),
    ("Trường ĐH Cảnh sát", 10.8650, 106.6600, "quan-12", "university"),
    ("Sân bay Tân Sơn Nhất", 10.8189, 106.6524, "quan-12", "landmark"),
    ("Cầu vượt Gò Vấp", 10.8250, 106.6800, "quan-12", "landmark"),

    # ---- Bình Thạnh (additional) ------------------------------------------
    ("Vinhomes Landmark 71", 10.7972, 106.7250, "binh-thanh", "landmark"),
    ("SC Pearl Plaza", 10.8035, 106.7170, "binh-thanh", "mall"),
    ("SC Iland Building", 10.8005, 106.7130, "binh-thanh", "landmark"),
    ("Bến phà Thanh Đa", 10.8050, 106.7250, "binh-thanh", "landmark"),
    ("Cầu Phú Mỹ", 10.7950, 106.7200, "binh-thanh", "landmark"),
    ("Cầu Bông", 10.7890, 106.7100, "binh-thanh", "landmark"),
    ("Cầu Đem Xá", 10.8020, 106.7080, "binh-thanh", "landmark"),
    ("Chợ Bình Điền", 10.7920, 106.7010, "binh-thanh", "market"),
    ("Trường ĐH Giao thông Vận tải", 10.8040, 106.7100, "binh-thanh", "university"),
    ("Bệnh viện Đa khoa Bình Thạnh", 10.8030, 106.7060, "binh-thanh", "hospital"),
    ("Công viên Văn Thánh", 10.7955, 106.7175, "binh-thanh", "park"),
    ("Bến xe Miền Đông (cũ)", 10.8020, 106.7050, "binh-thanh", "landmark"),
    ("Cầu Bình Tri 1", 10.7940, 106.7030, "binh-thanh", "landmark"),
    ("Sân Golf Rạch Sỹ", 10.8080, 106.7150, "binh-thanh", "sports"),

    # ---- Gò Vấp (additional) ---------------------------------------------
    ("SC Lotte Mart Gò Vấp", 10.8310, 106.6790, "go-vap", "mall"),
    ("Chợ Bà Hoa", 10.8340, 106.6820, "go-vap", "market"),
    ("Cầu vượt Nguyễn Oanh", 10.8300, 106.6860, "go-vap", "landmark"),
    ("Khu công nghiệp Lê Minh Xuân", 10.8450, 106.6600, "go-vap", "landmark"),
    ("Bệnh viện Đa khoa Gò Vấp", 10.8335, 106.6850, "go-vap", "hospital"),
    ("Trường ĐH Văn hóa TP.HCM", 10.8365, 106.6840, "go-vap", "university"),
    ("Trường ĐH Sư phạm Kỹ thuật", 10.8725, 106.7575, "go-vap", "university"),
    ("Trường ĐH An ninh Nhân dân", 10.8420, 106.6770, "go-vap", "university"),
    ("Khu Công nghiệp Tân Bửu", 10.8500, 106.6700, "go-vap", "landmark"),

    # ---- Phú Nhuận (additional) -------------------------------------------
    ("SC Starlight", 10.8025, 106.6885, "phu-nhuan", "mall"),
    ("SC Aeon Mall Tan Phu", 10.8031, 106.6265, "phu-nhuan", "mall"),
    ("Cầu Nguyễn Kiệm", 10.8030, 106.6830, "phu-nhuan", "landmark"),
    ("Cầu Trung Lương", 10.8020, 106.6750, "phu-nhuan", "landmark"),
    ("Trường ĐH Ngân hàng", 10.7788, 106.6972, "phu-nhuan", "university"),
    ("Bệnh viện Da liễu", 10.8035, 106.6860, "phu-nhuan", "hospital"),

    # ---- Tân Bình (additional) -------------------------------------------
    ("SC Emart Gò Vấp", 10.8310, 106.6790, "tan-binh", "mall"),
    ("SC SC Lotte Center", 10.7945, 106.6630, "tan-binh", "mall"),
    ("SC Sense City", 10.7940, 106.6590, "tan-binh", "mall"),
    ("Cầu Lộc Hòa", 10.8060, 106.6520, "tan-binh", "landmark"),
    ("Khu công nghiệp Tân Bình", 10.8080, 106.6400, "tan-binh", "landmark"),
    ("Công viên Gò Dầu", 10.8120, 106.6470, "tan-binh", "park"),
    ("Cầu Bà Quẹo", 10.7960, 106.6550, "tan-binh", "landmark"),
    ("Chợ Tân Bình", 10.7990, 106.6530, "tan-binh", "market"),
    ("Trường ĐH Văn hóa", 10.8030, 106.6510, "tan-binh", "university"),
    ("Bệnh viện Quân Y 175", 10.8025, 106.6635, "tan-binh", "hospital"),
    ("Sân Golf Tân Bình", 10.8110, 106.6440, "tan-binh", "sports"),
    ("Trường ĐH Y khoa Phạm Ngọc Thạch", 10.7645, 106.6730, "tan-binh", "university"),

    # ---- Tân Phú (additional) ---------------------------------------------
    ("SC Aeon Mall Celadon", 10.8031, 106.6265, "tan-phu", "mall"),
    ("SC Nowzone", 10.7975, 106.6220, "tan-phu", "mall"),
    ("SC Van Hanh Mall", 10.7940, 106.6180, "tan-phu", "mall"),
    ("Chợ Tân Phú", 10.8060, 106.6280, "tan-phu", "market"),
    ("Cầu Bà Điểm", 10.8070, 106.6140, "tan-phu", "landmark"),
    ("Khu công nghiệp Tân Bửu", 10.8150, 106.6080, "tan-phu", "landmark"),
    ("Công viên Tân Trào", 10.8045, 106.6310, "tan-phu", "park"),
    ("Trường ĐH Nguyễn Trãi", 10.8010, 106.6290, "tan-phu", "university"),
    ("Bệnh viện Quận Tân Phú", 10.8065, 106.6320, "tan-phu", "hospital"),

    # ---- Bình Tân (additional) -------------------------------------------
    ("SC Aeon Mall Bình Tân", 10.7140, 106.6122, "binh-tan", "mall"),
    ("Chợ Bình Tân", 10.7135, 106.6115, "binh-tan", "market"),
    ("Khu công nghiệp An Hạ", 10.7180, 106.6010, "binh-tan", "landmark"),
    ("Khu công nghiệp Vĩnh Lộc", 10.7200, 106.5850, "binh-tan", "landmark"),
    ("Bệnh viện Bình Tân", 10.7150, 106.6140, "binh-tan", "hospital"),
    ("Cầu An Hạ", 10.7160, 106.6070, "binh-tan", "landmark"),
    ("Cầu Vĩnh Bình", 10.7120, 106.5960, "binh-tan", "landmark"),
    ("Trường ĐH Lạc Hồng", 10.7170, 106.6180, "binh-tan", "university"),
    ("Trường ĐH Kỹ thuật Công nghệ", 10.7190, 106.6130, "binh-tan", "university"),

    # ---- Hóc Môn (additional) -------------------------------------------
    ("Bến xe Hóc Môn", 10.9040, 106.5920, "hoc-mon", "landmark"),
    ("Chợ Hóc Môn", 10.9025, 106.5940, "hoc-mon", "market"),
    ("Khu công nghiệp Hóc Môn", 10.9080, 106.5800, "hoc-mon", "landmark"),
    ("Trường ĐH Nông Lâm", 10.8855, 106.7755, "hoc-mon", "university"),
    ("Trường ĐH Bách Việt", 10.9060, 106.5880, "hoc-mon", "university"),
    ("Bệnh viện Đa khoa Hóc Môn", 10.9050, 106.5960, "hoc-mon", "hospital"),
    ("Cầu Bến Cối", 10.9090, 106.6020, "hoc-mon", "landmark"),
    ("Hồ Đền Xã", 10.9110, 106.5950, "hoc-mon", "landmark"),
    ("Đường tỉnh 8", 10.9150, 106.5900, "hoc-mon", "landmark"),

    # ---- Bình Chánh (additional) -----------------------------------------
    ("Bến xe Miền Tây", 10.7524, 106.6205, "binh-chanh", "landmark"),
    ("SC Aeon Mall Bình Chánh", 10.7605, 106.5750, "binh-chanh", "mall"),
    ("Chợ Bình Chánh", 10.7602, 106.5745, "binh-chanh", "market"),
    ("Khu công nghiệp Lê Minh Xuân", 10.7700, 106.5600, "binh-chanh", "landmark"),
    ("Khu công nghiệp Vĩnh Lộc", 10.7750, 106.5550, "binh-chanh", "landmark"),
    ("Bệnh viện Quốc tế Bình Chánh", 10.7605, 106.5750, "binh-chanh", "hospital"),
    ("Trường ĐH Tài nguyên Môi trường", 10.7630, 106.5780, "binh-chanh", "university"),
    ("Cầu Bình Điền", 10.7650, 106.5800, "binh-chanh", "landmark"),
    ("Cầu Chữ Yên", 10.7580, 106.5700, "binh-chanh", "landmark"),

    # ---- Củ Chi (additional) ---------------------------------------------
    ("Đường Hầm Củ Chi", 11.0788, 106.4928, "cu-chi", "landmark"),
    ("Khu di tích lịch sử Củ Chi", 11.0750, 106.4950, "cu-chi", "landmark"),
    ("Bến xe Củ Chi", 11.0740, 106.4930, "cu-chi", "landmark"),
    ("Khu công nghiệp Củ Chi", 11.0800, 106.4800, "cu-chi", "landmark"),
    ("Trường ĐH Củ Chi", 11.0770, 106.4980, "cu-chi", "university"),
    ("Bệnh viện Đa khoa Củ Chi", 11.0760, 106.4950, "cu-chi", "hospital"),
    ("Cầu Mỹ Thuận (gần Củ Chi)", 11.0650, 106.5000, "cu-chi", "landmark"),
    ("Đất Hót Củ Chi", 11.0880, 106.4850, "cu-chi", "landmark"),
    ("Chợ Củ Chi", 11.0745, 106.4940, "cu-chi", "market"),
    ("Trạm Biến áp Củ Chi", 11.0720, 106.4900, "cu-chi", "landmark"),

    # ---- Cần Giờ (additional) -------------------------------------------
    ("Bãi Biển Cần Giờ", 10.4008, 106.9272, "can-gio", "landmark"),
    ("Rừng Ngập Mặn Cần Giờ", 10.4050, 106.9300, "can-gio", "landmark"),
    ("Trung tâm Cần Giờ", 10.4030, 106.9250, "can-gio", "landmark"),
    ("Khu du lịch Bình Châu", 10.4120, 106.9350, "can-gio", "landmark"),
    ("Đảo Heo Gió", 10.3900, 106.9200, "can-gio", "landmark"),
    ("Đảo Khỉ", 10.3950, 106.9150, "can-gio", "landmark"),
    ("Bến tàu Cần Giờ", 10.4040, 106.9260, "can-gio", "landmark"),
    ("Khu bảo tồn chim", 10.4100, 106.9280, "can-gio", "landmark"),
    ("Trường ĐH Cần Giờ", 10.4070, 106.9220, "can-gio", "university"),
    ("Bệnh viện Cần Giờ", 10.4050, 106.9240, "can-gio", "hospital"),

    # ---- Nhà Bè (additional) ---------------------------------------------
    ("Nhà Bè Town", 10.7065, 106.7060, "nha-be", "landmark"),
    ("Khu công nghiệp Nhà Bè", 10.7100, 106.7000, "nha-be", "landmark"),
    ("Khu công nghiệp Hiệp Phước", 10.7150, 106.6950, "nha-be", "landmark"),
    ("Cầu Kênh T2", 10.7070, 106.7080, "nha-be", "landmark"),
    ("Cầu Long Thới", 10.7030, 106.7140, "nha-be", "landmark"),
    ("Chợ Nhà Bè", 10.7060, 106.7065, "nha-be", "market"),
    ("Trường ĐH Nam Cần", 10.7055, 106.7080, "nha-be", "university"),
    ("Bệnh viện Nhà Bè", 10.7070, 106.7050, "nha-be", "hospital"),
    ("Khu du lịch Long Hải", 10.7020, 106.7100, "nha-be", "landmark"),
    ("Cầu Rạch Đỉnh", 10.7000, 106.7150, "nha-be", "landmark"),

    # ---- New malls and shopping centers (various districts) ---------------
    ("SC SC Aeon Mall Tan Phu Celadon", 10.8031, 106.6265, None, "mall"),
    ("SC SC Vincom Center Landmark 81", 10.7954, 106.7226, None, "mall"),
    ("SC SC Vincom Center Q5", 10.7505, 106.6540, None, "mall"),
    ("SC SC Vincom Center Thu Duc", 10.8501, 106.7531, None, "mall"),
    ("SC SC Vincom Mega Mall", 10.7298, 106.7160, None, "mall"),
    ("SC Emart Gò Vấp", 10.8310, 106.6790, None, "mall"),
    ("SC Lotte Mart Đakao", 10.7800, 106.7040, None, "mall"),
    ("SC Lotte Mart Go Vap", 10.8310, 106.6790, None, "mall"),
    ("SC SC Nowzone", 10.7975, 106.6220, None, "mall"),
    ("SC SC Van Hanh Mall", 10.7940, 106.6180, None, "mall"),
    ("SC SC Sense City", 10.7940, 106.6590, None, "mall"),
    ("SC SC Parkson", 10.7715, 106.6950, None, "mall"),
    ("SC SC Takashimaya", 10.7732, 106.6940, None, "mall"),
    ("SC SC Diamond Plaza", 10.7806, 106.6930, None, "mall"),
    ("SC SC Saigon Centre", 10.7785, 106.7005, None, "mall"),
    ("SC SC Union Square", 10.7780, 106.7000, None, "mall"),
    ("SC SC Bitexco", 10.7716, 106.7040, None, "mall"),
    ("SC SC崩塘 (崩塘市場)", 10.7510, 106.6410, None, "mall"),
    ("SC SC Landmark 81 Tower", 10.7954, 106.7226, None, "mall"),
    ("SC SC Times Square", 10.7680, 106.7070, None, "mall"),
    ("SC SC Zen Plaza Q7", 10.7315, 106.7250, None, "mall"),
    ("SC SC crescents mall", 10.7285, 106.7230, None, "mall"),
    ("SC SC Huyndai Department Store", 10.7350, 106.7340, None, "mall"),
    ("SC SC Satra Mall", 10.7600, 106.6600, None, "mall"),
    ("SC SC Big C", 10.7600, 106.6600, None, "mall"),
    ("SC SC GO!", 10.7600, 106.6600, None, "mall"),
    ("SC SC Co.opmart", 10.7650, 106.6600, None, "mall"),
    ("SC SC WinMart", 10.7600, 106.6600, None, "mall"),
    ("SC SC MM Mega Market", 10.8000, 106.6600, None, "mall"),

    # ---- Universities and schools (various) -------------------------------
    ("Trường ĐH Quốc tế Hồng Bàng", 10.8060, 106.6790, None, "university"),
    ("Trường ĐH Văn Lang", 10.7480, 106.6550, None, "university"),
    ("Trường ĐH Kinh tế Luật", 10.8370, 106.6790, None, "university"),
    ("Trường ĐH Ngoại thương", 10.7695, 106.6885, None, "university"),
    ("Trường ĐH Thủy Lợi", 10.7855, 106.6625, None, "university"),
    ("Trường ĐH Giao thông Vận tải", 10.8040, 106.7100, None, "university"),
    ("Trường ĐH Mở TP.HCM", 10.7355, 106.6860, None, "university"),
    ("Trường ĐH Nguyễn Tất Thành", 10.7520, 106.6400, None, "university"),
    ("Trường ĐH Lê Quý Đôn", 10.7600, 106.6530, None, "university"),
    ("Trường ĐH Văn hóa", 10.8030, 106.6510, None, "university"),
    ("Trường ĐH Sư phạm TDTT", 10.7790, 106.6845, None, "university"),
    ("Trường ĐH Công đoàn", 10.7735, 106.6820, None, "university"),
    ("Trường ĐH Tài chính Kế toán", 10.7835, 106.6810, None, "university"),
    ("Trường ĐH Kinh doanh Công nghệ", 10.7355, 106.6860, None, "university"),
    ("Trường ĐH Quốc tế Sài Gòn", 10.8060, 106.6790, None, "university"),
    ("Trường ĐH Sài Gòn", 10.8555, 106.6500, None, "university"),
    ("Trường ĐH Tân Tạo", 10.7715, 106.6100, None, "university"),
    ("Trường ĐH Bình Dương", 11.1500, 106.6500, None, "university"),
    ("Trường ĐH Thủ Dầu Một", 10.9800, 106.6500, None, "university"),
    ("Trường PTTH Chuyên LHP", 10.7805, 106.6955, None, "school"),
    ("Trường PTTH Trần Đại Nghĩa", 10.7630, 106.6823, None, "school"),
    ("Trường PTTH NKP", 10.7710, 106.7000, None, "school"),
    ("Trường Quốc tế Canada (CIS)", 10.7305, 106.7175, None, "school"),
    ("Trường Quốc tế Hồng Kông (HIS)", 10.7290, 106.7200, None, "school"),

    # ---- Hospitals (various) ----------------------------------------------
    ("Bệnh viện Chợ Rẫy", 10.7875, 106.6863, None, "hospital"),
    ("Bệnh viện Nhi Đồng 1", 10.7876, 106.6978, None, "hospital"),
    ("Bệnh viện Nhi Đồng 2", 10.7525, 106.6510, None, "hospital"),
    ("Bệnh viện Từ Dũ", 10.7836, 106.6780, None, "hospital"),
    ("Bệnh viện Nhân Dân Gia Định", 10.7460, 106.6540, None, "hospital"),
    ("Bệnh viện Gia Định", 10.8025, 106.7050, None, "hospital"),
    ("Bệnh viện Quân Y 175", 10.8025, 106.6635, None, "hospital"),
    ("Bệnh viện FV", 10.7298, 106.7220, None, "hospital"),
    ("Bệnh viện Tim Tâm Đức", 10.7310, 106.7190, None, "hospital"),
    ("Bệnh viện Bình Dân", 10.7715, 106.6755, None, "hospital"),
    ("Bệnh viện Thống Nhất", 10.7828, 106.6745, None, "hospital"),
    ("Bệnh viện Bệnh Nhiệt đới", 10.7640, 106.6560, None, "hospital"),
    ("Bệnh viện Phạm Ngọc Thạch", 10.7870, 106.6435, None, "hospital"),
    ("Bệnh viện Tai Mũi Họng", 10.7860, 106.6470, None, "hospital"),
    ("Bệnh viện Da liễu", 10.8035, 106.6860, None, "hospital"),
    ("Bệnh viện Y học Cổ truyền", 10.8580, 106.6475, None, "hospital"),
    ("Bệnh viện Quốc tế Columbia Asia", 10.8030, 106.7060, None, "hospital"),
    ("Bệnh viện Vinmec Central Park", 10.7832, 106.7108, None, "hospital"),
    ("Bệnh viện Vinmec Times City", 10.7680, 106.7070, None, "hospital"),
    ("Bệnh viện ĐK Thanh Nhàn", 10.7876, 106.6978, None, "hospital"),

    # ---- Parks and tourist attractions ------------------------------------
    ("Công viên Tao Đàn", 10.7906, 106.6883, None, "park"),
    ("Công viên 30/4", 10.7680, 106.6730, None, "park"),
    ("Công viên Lê Văn Tam", 10.7796, 106.6800, None, "park"),
    ("Công viên Gia Định", 10.7830, 106.6750, None, "park"),
    ("Công viên Văn Thánh", 10.7955, 106.7175, None, "park"),
    ("Công viên Tao Đàn", 10.7906, 106.6883, None, "park"),
    ("Đầm Sen Park", 10.7650, 106.6380, None, "landmark"),
    ("Khu Du lịch Đầm Sen", 10.7655, 106.6390, None, "landmark"),
    ("Khu Du lịch Suối Tiên", 10.8920, 106.8300, None, "landmark"),
    ("Khu Du lịch Bửu Long", 10.8680, 106.8210, None, "landmark"),
    ("Thảo Cầm Viên Sài Gòn", 10.7870, 106.6990, None, "landmark"),
    ("Khu Du lịch Long Hải", 10.7020, 106.7100, None, "landmark"),
    ("Khu Du lịch Bình Châu", 10.4120, 106.9350, None, "landmark"),
    ("Núi Bà Đen", 11.3500, 106.1500, None, "landmark"),
    ("Dinh Độc Lập", 10.7828, 106.6979, None, "landmark"),
    ("Nhà Hát Lớn TP.HCM", 10.7765, 106.6990, None, "landmark"),
    ("Bảo Tàng Lịch Sử", 10.7865, 106.6985, None, "landmark"),
    ("Bảo Tàng TP.HCM", 10.7766, 106.6923, None, "landmark"),
    ("Bảo Tàng Hồ Chí Minh", 10.7828, 106.6979, None, "landmark"),
    ("Bảo Tàng Mỹ thuật", 10.7790, 106.6860, None, "landmark"),
    ("Chợ Bến Thành", 10.7797, 106.6983, None, "landmark"),
    ("Cầu Thị Nghè", 10.7895, 106.7125, None, "landmark"),
    ("Cầu Phú Mỹ", 10.7950, 106.7200, None, "landmark"),
    ("Cầu Bông", 10.7890, 106.7100, None, "landmark"),
    ("Cầu Thủ Thiêm", 10.7940, 106.7240, None, "landmark"),
    ("Landmark 81", 10.7954, 106.7226, None, "landmark"),
    ("Bitexco Financial Tower", 10.7716, 106.7040, None, "landmark"),
    ("Saigon Centre", 10.7785, 106.7005, None, "landmark"),
    ("Diamond Plaza", 10.7806, 106.6930, None, "landmark"),
    ("Times Square", 10.7680, 106.7070, None, "landmark"),

    # ---- Government buildings ---------------------------------------------
    ("Trụ sở UBND TP.HCM", 10.7825, 106.7000, None, "government"),
    ("Trụ sở Bộ GTVT", 10.7795, 106.6980, None, "government"),
    ("Trụ sở Bộ Xây dựng", 10.7780, 106.6990, None, "government"),
    ("Tòa nhà Bộ Quốc phòng", 10.7815, 106.6955, None, "government"),
    ("Tòa nhà Bộ Công an", 10.7810, 106.6930, None, "government"),
    ("Sở GTVT TP.HCM", 10.7820, 106.6985, None, "government"),
    ("Cảng Sài Gòn", 10.7660, 106.7150, None, "landmark"),
    ("Cảng Cát Lái", 10.8230, 106.7430, None, "landmark"),

    # ---- Sports venues ---------------------------------------------------
    ("Sân vận động Thống Nhất", 10.7828, 106.6745, None, "sports"),
    ("Sân vận động Quân khu 7", 10.7940, 106.7175, None, "sports"),
    ("Sân Golf Rạch Chiếc", 10.8870, 106.7990, None, "sports"),
    ("Sân Golf Tân Bình", 10.8110, 106.6440, None, "sports"),
    ("Sân Golf Đại Phong", 10.8820, 106.7950, None, "sports"),
    ("Sân Golf Him Lam", 10.7750, 106.7060, None, "sports"),
    ("Sân Golf Bình Dương", 11.1500, 106.6500, None, "sports"),
    ("Sân Tennis Lam Sơn", 10.7790, 106.6830, None, "sports"),
    ("Trung tâm TDTT Quận 7", 10.7300, 106.7200, None, "sports"),
    ("Trung tâm Hội chợ Sài Gòn", 10.7340, 106.7280, None, "landmark"),

    # ---- Markets --------------------------------------------------------
    ("Chợ Bến Thành", 10.7797, 106.6983, None, "market"),
    ("Chợ Bình Tây", 10.7495, 106.6365, None, "market"),
    ("Chợ Tây Phường", 10.7505, 106.6380, None, "market"),
    ("Chợ Kim Biên", 10.7510, 106.6420, None, "market"),
    ("Chợ Hòa Hảo", 10.7670, 106.6710, None, "market"),
    ("Chợ Gò Vấp", 10.8390, 106.6840, None, "market"),
    ("Chợ Bình Thạnh", 10.8015, 106.7035, None, "market"),
    ("Chợ Tân Phú", 10.8060, 106.6280, None, "market"),
    ("Chợ Bình Tân", 10.7135, 106.6115, None, "market"),
    ("Chợ Hóc Môn", 10.9025, 106.5940, None, "market"),
    ("Chợ Bình Chánh", 10.7602, 106.5745, None, "market"),
    ("Chợ Củ Chi", 11.0745, 106.4940, None, "market"),
    ("Chợ Bến xe Miền Tây", 10.7524, 106.6205, None, "market"),
    ("Chợ Xóm Hới", 10.7595, 106.7030, None, "market"),
    ("Chợ Nhị Yên", 10.7500, 106.6400, None, "market"),
    ("Chợ Lò Rèn", 10.7450, 106.6530, None, "market"),
    ("Chợ Bình Đông", 10.7480, 106.6820, None, "market"),
    ("Chợ Sáng Tây", 10.7685, 106.6715, None, "market"),
    ("Chợ Hòa Bình", 10.7625, 106.6410, None, "market"),
    ("Chợ Tân Hưng Thuận", 10.8600, 106.6540, None, "market"),
    ("Chợ Quận 12", 10.8570, 106.6480, None, "market"),
    ("Chợ Nhà Bè", 10.7060, 106.7065, None, "market"),
]


def _district_order() -> dict[str, int]:
    return {
        "quan-1": 1,
        "quan-3": 2,
        "quan-4": 3,
        "quan-5": 4,
        "quan-6": 5,
        "quan-7": 6,
        "quan-8": 7,
        "thu-duc": 8,
        "quan-10": 9,
        "quan-11": 10,
        "quan-12": 11,
        "binh-thanh": 12,
        "go-vap": 13,
        "phu-nhuan": 14,
        "tan-binh": 15,
        "tan-phu": 16,
        "binh-tan": 17,
        "hoc-mon": 18,
        "binh-chanh": 19,
        "cu-chi": 20,
        "can-gio": 21,
        "nha-be": 22,
    }


def _slug_to_display(slug: str) -> str:
    mapping = {
        "quan-1": "Quận 1",
        "quan-3": "Quận 3",
        "quan-4": "Quận 4",
        "quan-5": "Quận 5",
        "quan-6": "Quận 6",
        "quan-7": "Quận 7",
        "quan-8": "Quận 8",
        "thu-duc": "Thủ Đức",
        "quan-10": "Quận 10",
        "quan-11": "Quận 11",
        "quan-12": "Quận 12",
        "binh-thanh": "Bình Thạnh",
        "go-vap": "Gò Vấp",
        "phu-nhuan": "Phú Nhuận",
        "tan-binh": "Tân Bình",
        "tan-phu": "Tân Phú",
        "binh-tan": "Bình Tân",
        "hoc-mon": "Hóc Môn",
        "binh-chanh": "Bình Chánh",
        "cu-chi": "Củ Chi",
        "can-gio": "Cần Giờ",
        "nha-be": "Nhà Bè",
    }
    return mapping.get(slug, slug)


def _clean_name(name: str) -> str:
    """Remove existing district suffix from name to avoid duplication."""
    suffixes = [
        ", Quận 1", ", Quận 3", ", Quận 4", ", Quận 5", ", Quận 6",
        ", Quận 7", ", Quận 8", ", Quận 10", ", Quận 11", ", Quận 12",
    ]
    for s in suffixes:
        if name.endswith(s):
            name = name[: -len(s)]
    return name.strip()


def seed_from_presets() -> int:
    """Import locations from streamlit_app.data.presets.HCM_PRESETS."""
    from streamlit_app.data.presets import HCM_PRESETS

    count = 0
    current_district_slug: str | None = None
    current_district_name: str | None = None
    order_map = _district_order()

    for label, lat, lon in HCM_PRESETS:
        if lat is None:
            if label.startswith("· ") and " ·" in label:
                slug = _label_to_slug(label)
                if slug:
                    current_district_slug = slug
                    current_district_name = _slug_to_display(slug)
                    order = order_map.get(slug, 99)
                    upsert_district(current_district_name, order)
        else:
            if current_district_slug is None:
                current_district_name = None
            clean = _clean_name(label)
            add_location(clean, lat, lon, district=current_district_name)
            count += 1

    return count


def _label_to_slug(label: str) -> str | None:
    """Extract district slug from HCM_PRESETS header label."""
    label = label.strip()
    mapping = {
        "· Quận 1 ·": "quan-1",
        "· Quận 3 ·": "quan-3",
        "· Quận 4 ·": "quan-4",
        "· Quận 5 ·": "quan-5",
        "· Quận 6 ·": "quan-6",
        "· Quận 7 ·": "quan-7",
        "· Quận 8 ·": "quan-8",
        "· Quận 9 / Thủ Đức ·": "thu-duc",
        "· Quận 10 ·": "quan-10",
        "· Quận 11 ·": "quan-11",
        "· Quận 12 ·": "quan-12",
        "· Bình Thạnh ·": "binh-thanh",
        "· Gò Vấp ·": "go-vap",
        "· Phú Nhuận ·": "phu-nhuan",
        "· Tân Bình ·": "tan-binh",
        "· Tân Phú ·": "tan-phu",
        "· Bình Tân ·": "binh-tan",
        "· Hóc Môn ·": "hoc-mon",
        "· Bình Chánh ·": "binh-chanh",
        "· Củ Chi ·": "cu-chi",
        "· Cần Giờ ·": "can-gio",
        "· Nhà Bè ·": "nha-be",
    }
    return mapping.get(label)


def seed_extended() -> int:
    """Seed the extended HCMC location list."""
    count = 0
    order_map = _district_order()

    for name, lat, lon, district_slug, category in HCMC_LOCATIONS:
        display_name = _slug_to_display(district_slug) if district_slug else ""
        if district_slug is not None:
            order = order_map.get(district_slug, 99)
            upsert_district(display_name, order)
        add_location(name, lat, lon, category=category, district=display_name)
        count += 1

    return count


def main() -> None:
    print("Khởi tạo cơ sở dữ liệu...")
    init_db()

    preset_count = seed_from_presets()
    print(f"Đã nhập {preset_count} địa điểm từ HCM_PRESETS.")

    extended_count = seed_extended()
    print(f"Đã nhập {extended_count} địa điểm mở rộng.")

    total = get_location_count()
    district_total = get_district_count()
    print(f"\nTổng cộng: {total} địa điểm, {district_total} quận/huyện.")


if __name__ == "__main__":
    main()
