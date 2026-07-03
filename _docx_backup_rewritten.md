# XÂY DỰNG HỆ THỐNG DỰ BÁO MỨC ĐỘ ÙN TẮC GIAO THÔNG PHỤC VỤ GIAO THÔNG TẠI TP.HCM BẰNG MÔ HÌNH STACKING ENSEMBLE VÀ DỮ LIỆU GIAO THÔNG ĐÔ THỊ

**BỘ XÂY DỰNG**
**TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI TP.HỒ CHÍ MINH**
**VIỆN CÔNG NGHỆ THÔNG TIN VÀ ĐIỆN, ĐIỆN TỬ**

----- **&** -----

**Môn học:** Chuyên đề hệ thống giao thông thông minh
**GVHD:** Vũ Đình Long
**Mã lớp học phần:** 012012203810
**Năm học:** 2025 – 2026

**TP. Hồ Chí Minh, tháng 06 năm 2026**

---

## BẢNG PHÂN CÔNG NHIỆM VỤ

| STT | Họ và tên | MSSV | Chức vụ | Nhiệm vụ | Đánh giá mức độ hoàn thành (%) |
|-----|-----------|------|---------|---------|-------------------------------|
| 1 | Võ Anh Nhật | 052206007980 | Nhóm trưởng | Xây dựng hệ thống dự báo LOS, giao diện web | 100% |

---

## LỜI CẢM ƠN

Trước hết, nhóm chúng em xin bày tỏ lòng biết ơn chân thành và sâu sắc đến Thầy Vũ Đình Long, giảng viên môn Chuyên đề Hệ thống Giao thông Thông minh, Trường Đại học Giao thông Vận tải, đã tận tình hướng dẫn, hỗ trợ và định hướng cho nhóm trong quá trình thực hiện đề tài "Xây dựng hệ thống dự báo mức độ ùn tắc giao thông phục vụ giao thông tại TP.HCM bằng mô hình Stacking Ensemble và dữ liệu giao thông đô thị".

Trong suốt quá trình nghiên cứu và hoàn thiện đề tài, những góp ý chuyên môn, sự chỉ dẫn khoa học và tinh thần hỗ trợ tận tâm của Thầy đã giúp nhóm chúng em hiểu rõ hơn về vai trò của hệ thống giao thông thông minh trong quản lý, giám sát và tối ưu hóa giao thông đô thị. Đặc biệt, các kiến thức được Thầy truyền đạt trong học phần đã tạo nền tảng quan trọng để nhóm vận dụng tư duy hệ thống, dữ liệu giao thông và mô hình học máy vào bài toán dự báo ùn tắc giao thông tại TP.HCM.

Nhóm chúng em xin chân thành cảm ơn Thầy vì đã luôn tạo điều kiện, động viên và định hướng để nhóm có thể tiếp cận đề tài một cách nghiêm túc, khoa học và thực tiễn hơn. Mặc dù nhóm đã cố gắng trong quá trình thực hiện, đề tài khó tránh khỏi những thiếu sót nhất định. Chúng em rất mong tiếp tục nhận được những ý kiến đóng góp quý báu từ Thầy để bài nghiên cứu được hoàn thiện hơn.

Một lần nữa, nhóm chúng em xin kính chúc Thầy Vũ Đình Long thật nhiều sức khỏe, hạnh phúc và thành công trong sự nghiệp giảng dạy, nghiên cứu khoa học và công tác chuyên môn.

---

## TÓM TẮT ĐỀ TÀI

Đề tài nghiên cứu và triển khai một Hệ thống Giao thông Thông minh (Intelligent Transportation System – ITS) dành cho Thành phố Hồ Chí Minh (TP.HCM), một trong những đô thị có mật độ giao thông cao nhất khu vực Đông Nam Á. Hệ thống được xây dựng với hai chức năng cốt lõi: (1) dự đoán Mức phục vụ Giao thông (Level of Service – LOS) cho 84.633 đoạn đường trên toàn thành phố theo 6 cấp A–F theo tiêu chuẩn Highway Capacity Manual (HCM); và (2) tìm đường đi tối ưu dựa trên trạng thái giao thông thời gian thực sử dụng thuật toán Dijkstra và A*.

Mô hình dự đoán LOS sử dụng kiến trúc Stacking Ensemble kết hợp 4 base learner: Random Forest (RF), XGBoost, LightGBM và CatBoost, với Logistic Regression làm meta-learner. Mô hình được huấn luyện trên 149 đặc trưng bao gồm đặc trưng thời gian, không gian, mạng lưới đường và tương tác. Hiệu suất đạt độ chính xác xác thực (validation accuracy) 74,9% và Macro F1 67,5% trên tập validation; Cross-validation 3-fold đạt accuracy 90,4% ± 0,5% và Macro F1 86,8% ± 0,8%. Hệ thống còn tích hợp module tìm đường tối ưu với 3 chiến lược: khoảng cách ngắn nhất, thời gian nhanh nhất, và ít tắc nghẽn nhất dựa trên LOS, sử dụng chỉ số không gian BallTree cho truy vấn láng giềng gần O(log n).

---

## MỤC LỤC

- Chương 1. Giới Thiệu Đề Tài
  - 1.1. Lý do chọn đề tài và bối cảnh giao thông đô thị và nhu cầu dự báo tình trạng giao thông
  - 1.2. Mục tiêu của đề tài
  - 1.3. Phạm vi nghiên cứu
  - 1.4. Đối tượng nghiên cứu
  - 1.5. Phương pháp thực hiện
  - 1.6. Ý nghĩa thực tiễn của đề tài
- Chương 2. Cơ Sở Lý Thuyết
  - 2.1. Khái niệm mức độ phục vụ giao thông LOS
  - 2.2. Tổng quan các mô hình, thuật toán được sử dụng và các công trình liên quan
    - 2.2.1. Phương pháp Stacking Ensemble trong dự đoán giao thông
    - 2.2.2. XGBoost, LightGBM và CatBoost trong dự đoán ùn tắc giao thông
    - 2.2.3. Thuật toán Dijkstra và A* trong tìm đường tối ưu đô thị
    - 2.2.4. NetworkX cho phân tích mạng lưới giao thông đô thị
    - 2.2.5. Tối ưu siêu tham số với Optuna
    - 2.2.6. BallTree cho truy vấn láng giềng không gian
- Chương 3. Dữ Liệu Và Phương Pháp Xử Lý
  - 3.1. Thu thập dữ liệu
  - 3.2. Tiền xử lý dữ liệu
    - 3.2.1. Chi tiết quy trình gộp dữ liệu
    - 3.2.2. Chi tiết quy trình làm sạch dữ liệu
  - 3.3. Trực quan hoá dữ liệu sau khi xử lý
  - 3.4. Xây dựng đặc trưng
  - 3.5. Chia tập train/test
- Chương 4. Xây Dựng Mô Hình Dự Báo LOS
  - 4.1. Tối ưu siêu tham số
  - 4.2. Kiến trúc mô hình Stacking Ensemble
  - 4.3. Sơ đồ luồng xử lý tìm đường tối ưu dựa trên đồ thị giao thông
- Chương 5. Kết Quả Thực Nghiệm Và Đánh Giá
  - 5.1. Kết quả dự báo trên tập kiểm thử
  - 5.2. Ma trận nhầm lẫn
  - 5.3. Biểu đồ Precision-Recall Curve đa lớp
  - 5.4. Phân tích phân bố cấp độ LOS dự báo và độ tin cậy của mô hình
  - 5.5. Những đặc trưng quan trọng mà mô hình học được và tạo ra
- Chương 6. Giao diện hệ thống
  - 6.1. Giao diện trang home của hệ thống
  - 6.2. Giao diện để người dùng tìm đường đi
- Chương 7. Kết Luận Và Hướng Phát Triển
  - 7.1. Kết Quả Đạt Được
  - 7.2. Hạn Chế Của Đề Tài
  - 7.3. Hướng Phát Triển Trong Tương Lai
  - 7.4. Khả Năng Mở Rộng Vào Hệ Thống ITS Thực Tế
- Chương 8. Công nghệ bản đồ & tìm đường: GPS & map, các tiện ích khác
  - 8.1. Tổng quan công nghệ bản đồ và tìm đường trong hệ thống
  - 8.2. Công nghệ GPS và định vị thời gian thực
  - 8.3. Bản đồ tương tác (Interactive Map)
  - 8.4. Hệ thống tìm đường (Routing Engine)
  - 8.5. Cấu trúc đồ thị giao thông (Graph Caching)
  - 8.6. Chế độ dẫn đường toàn màn hình (Full-Screen Navigation)
  - 8.7. Tiện ích bổ sung: xuất GPX, lịch sử, yêu thích, đa điểm
  - 8.8. API Endpoint cho bản đồ & tìm đường
  - 8.9. Các thuật toán và công thức toán học cốt lõi
- Tài Liệu Tham Khảo

---

## DANH MỤC VIẾT TẮT

| STT | Từ viết tắt | Viết đầy đủ / Tên đầy đủ | Nghĩa trong bài báo cáo |
|-----|-------------|--------------------------|------------------------|
| 1 | ITS | Intelligent Transportation System | Hệ thống giao thông thông minh |
| 2 | TP.HCM | Thành phố Hồ Chí Minh | Khu vực nghiên cứu của đề tài |
| 3 | LOS | Level of Service | Mức độ phục vụ giao thông, phản ánh tình trạng lưu thông |
| 4 | HCM | Highway Capacity Manual | Bộ tiêu chuẩn đánh giá năng lực và mức phục vụ giao thông |
| 5 | RF | Random Forest | Thuật toán học máy cây quyết định ngẫu nhiên |
| 6 | GPS | Global Positioning System | Hệ thống định vị toàn cầu dùng để thu thập dữ liệu vị trí |
| 7 | AI | Artificial Intelligence | Trí tuệ nhân tạo |
| 8 | UTMC | Urban Traffic Management Center | Trung tâm Quản lý và Điều hành Giao thông Đô thị |
| 9 | CSV | Comma-Separated Values | Định dạng tệp dữ liệu dạng bảng |
| 10 | IoT | Internet of Things | Mạng lưới thiết bị cảm biến kết nối Internet |
| 11 | V/C | Volume-to-Capacity Ratio | Tỷ lệ lưu lượng giao thông trên năng lực thông hành |
| 12 | GRU | Gated Recurrent Unit | Mạng nơ-ron hồi tiếp dùng cho dữ liệu chuỗi thời gian |
| 13 | LSTM | Long Short-Term Memory | Mạng nơ-ron hồi tiếp có khả năng ghi nhớ dài hạn |
| 14 | GBM | Gradient Boosting Machine | Thuật toán tăng cường dựa trên gradient |
| 15 | XGBoost | Extreme Gradient Boosting | Thuật toán Gradient Boosting tối ưu hóa hiệu suất |
| 16 | LightGBM | Light Gradient Boosting Machine | Phiên bản Gradient Boosting nhẹ và tốc độ cao |
| 17 | GOSS | Gradient-based One-Side Sampling | Kỹ thuật lấy mẫu trong LightGBM |
| 18 | EFB | Exclusive Feature Bundling | Kỹ thuật gộp đặc trưng trong LightGBM |
| 19 | OTS | Ordered Target Statistics | Phương pháp mã hóa biến phân loại của CatBoost |
| 20 | SPP | Shortest Path Problem | Bài toán tìm đường đi ngắn nhất |
| 21 | OSMnx | OpenStreetMap Network Extraction | Thư viện khai thác mạng lưới đường từ OpenStreetMap |
| 22 | TPE | Tree-structured Parzen Estimator | Thuật toán tối ưu siêu tham số của Optuna |
| 23 | ML | Machine Learning | Học máy |
| 24 | kNN | k-Nearest Neighbors | Thuật toán tìm k láng giềng gần nhất |
| 25 | POI | Point of Interest | Điểm quan tâm trên bản đồ |
| 26 | AP | Average Precision | Độ chính xác trung bình trên đường Precision–Recall |
| 27 | OOF | Out-of-Fold | Dự đoán sinh ra từ Cross Validation dùng cho Stacking |
| 28 | L1 | Lasso Regularization | Chuẩn hóa L1 trong XGBoost |
| 29 | L2 | Ridge Regularization | Chuẩn hóa L2 trong Logistic Regression/XGBoost |
| 30 | API | Application Programming Interface | Giao diện lập trình ứng dụng phục vụ tích hợp hệ thống |
| 31 | EV | Electric Vehicle | Xe điện |
| 32 | TRB | Transportation Research Board | Hội đồng Nghiên cứu Giao thông Hoa Kỳ |
| 33 | DAML | Data Analysis and Machine Learning | Hội nghị Data Analysis and Machine Learning |
| 34 | ACM | Association for Computing Machinery | Hiệp hội Máy tính Hoa Kỳ |
| 35 | SIGKDD | Special Interest Group on Knowledge Discovery and Data Mining | Nhóm nghiên cứu khai phá dữ liệu của ACM |
| 36 | NeurIPS | Conference on Neural Information Processing Systems | Hội nghị quốc tế về hệ thống xử lý thông tin thần kinh |
| 37 | MDPI | Multidisciplinary Digital Publishing Institute | Nhà xuất bản học thuật của các bài báo tham khảo |

---

# Chương 1. Giới Thiệu Đề Tài

## 1.1. Lý do chọn đề tài và bối cảnh giao thông đô thị và nhu cầu dự báo tình trạng giao thông

TP.HCM là đô thị lớn nhất Việt Nam với dân số hơn 10 triệu người, đồng thời là trung tâm kinh tế – xã hội hàng đầu khu vực Đông Nam Á. Tốc độ tăng trưởng phương tiện cá nhân vượt xa tốc độ mở rộng hạ tầng giao thông, dẫn đến tình trạng ùn tắc giao thông ngày càng nghiêm trọng. Theo báo cáo của Sở Giao thông Vận tải TP.HCM, thành phố hiện có hơn 8 triệu xe máy và hơn 800.000 ô tô, trong khi hệ thống đường bộ chỉ đáp ứng khoảng 60–70% nhu cầu đi lại của người dân.

Thành phố đã triển khai nhiều giải pháp quản lý giao thông thông minh, bao gồm:

- **Hệ thống camera giám sát giao thông** và phát hiện vi phạm sử dụng AI.
- **Trung tâm Quản lý và Điều hành Giao thông Đô thị (UTMC)** — trung tâm điều phối giao thông tập trung lớn nhất Đông Nam Á.
- **Hệ thống điều khiển đèn tín hiệu** tại 188 nút giao thông.
- **Thu thập dữ liệu GPS** từ hơn 67.000 phương tiện giao thông công cộng (xe buýt, xe tải).
- **Ứng dụng công nghệ Digital Twin** trong mô phỏng và dự báo giao thông.

## 1.2. Mục tiêu của đề tài

Mục tiêu chính của đề tài được phát biểu thành hai bài toán con:

- **Bài toán 1 (Phân loại LOS):** Dự đoán cấp LOS (A–F) của 84.633 đoạn đường tại TP.HCM dựa trên dữ liệu lịch sử về lưu lượng xe, tốc độ dòng xe, và các đặc trưng không gian–thời gian liên quan.

- **Bài toán 2 (Tìm đường tối ưu):** Xác định tuyến đường tối ưu giữa hai vị trí bất kỳ trong mạng lưới giao thông TP.HCM theo ba chiến lược: khoảng cách, thời gian, hoặc ít tắc nghẽn nhất.

## 1.3. Phạm vi nghiên cứu

Phạm vi nghiên cứu của đề tài tập trung vào **dự báo mức độ ùn tắc giao thông tại TP.HCM** thông qua chỉ số **LOS**, dựa trên bộ dữ liệu giao thông đô thị đã có sẵn dưới dạng CSV, bao gồm thông tin về nút giao, đoạn đường, tuyến đường, vận tốc lịch sử và nhãn LOS.

Về không gian, đề tài nghiên cứu mạng lưới giao thông đường bộ tại TP.HCM với nhiều đoạn đường được mô hình hóa thành dữ liệu mạng lưới. Về chức năng, đề tài xây dựng quy trình xử lý dữ liệu, huấn luyện mô hình **Stacking Ensemble** để dự báo LOS, đồng thời triển khai giao diện dashboard hỗ trợ quan sát, dự báo nhanh và tìm đường theo trạng thái giao thông.

## 1.4. Đối tượng nghiên cứu

Đối tượng nghiên cứu của đề tài là **tình trạng ùn tắc giao thông đô thị tại TP.HCM**, được biểu diễn thông qua chỉ số **LOS** từ A đến F, trong đó **LOS A** thể hiện giao thông thông thoáng và **LOS F** thể hiện tắc nghẽn nghiêm trọng.

Bên cạnh đó, đề tài tập trung khai thác các dữ liệu liên quan như nút giao, đoạn đường, loại đường, vận tốc, thời điểm trong ngày, ngày trong tuần và đặc trưng không gian – thời gian. Trên cơ sở đó, mô hình **Stacking Ensemble** được áp dụng để phân loại và dự báo mức độ phục vụ giao thông cho từng đoạn đường.

## 1.5. Phương pháp thực hiện

Đề tài được thực hiện theo quy trình gồm: tìm hiểu cơ sở lý thuyết về ITS, chỉ số LOS, dự báo ùn tắc và các mô hình học máy; sau đó tiền xử lý dữ liệu giao thông, xử lý lỗi, dữ liệu thiếu, ngoại lai và xây dựng thêm các đặc trưng về thời gian, không gian, vận tốc lịch sử và mạng lưới đường.

Tiếp theo, nhóm xây dựng mô hình Stacking Ensemble kết hợp Random Forest, XGBoost, LightGBM, CatBoost và Logistic Regression làm meta-learner. Mô hình được huấn luyện, kiểm thử và đánh giá bằng Accuracy, Precision, Recall, F1-score và ma trận nhầm lẫn. Cuối cùng, kết quả được tích hợp vào giao diện ứng dụng để hỗ trợ trực quan hóa, dự báo nhanh và tìm đường.

## 1.6. Ý nghĩa thực tiễn của đề tài

Đề tài có ý nghĩa thực tiễn trong việc hỗ trợ dự báo mức độ ùn tắc giao thông đô thị tại TP.HCM, giúp người dùng nhận biết các khu vực có nguy cơ tắc nghẽn và lựa chọn lộ trình di chuyển phù hợp hơn.

Đối với cơ quan quản lý, mô hình dự báo LOS có thể hỗ trợ theo dõi tình trạng vận hành của mạng lưới đường, đánh giá mức độ tắc nghẽn và đề xuất phương án điều tiết giao thông hiệu quả.

Ngoài ra, đề tài còn có ý nghĩa học thuật khi kết hợp dữ liệu giao thông đô thị với mô hình học máy hiện đại, tạo nền tảng cho việc phát triển các hệ thống dự báo giao thông thời gian thực trong tương lai.

---

# Chương 2. Cơ Sở Lý Thuyết

## 2.1. Khái niệm mức độ phục vụ giao thông LOS

Mức phục vụ Giao thông (Level of Service – LOS) là chỉ số định tính mô tả chất lượng vận hành của một tuyến đường, được Transportation Research Board định nghĩa trong Highway Capacity Manual (HCM) [1]. LOS được phân thành 6 cấp từ A đến F, trong đó A biểu thị điều kiện giao thông tự do tốt nhất và F biểu thị tình trạng tắc nghẽn nghiêm trọng.

| Cấp LOS | Chất lượng | Tốc độ (km/h) | Tỷ lệ V/C |
|---------|-----------|---------------|-----------|
| A | Tự do | 80 | 0,00–0,60 |
| B | Hợp lý | 70 | 0,61–0,70 |
| C | Gần tự do | 60 | 0,71–0,80 |
| D | Dòng ổn định | 50 | 0,81–0,90 |
| E | Gần công suất | 40 | 0,91–1,00 |
| F | Tắc nghẽn | < 15 | > 1,00 |

**Bảng 1.** Bảng phân cấp LOS trong giao thông đô thị.

## 2.2. Tổng quan các mô hình, thuật toán được sử dụng và các công trình liên quan

### 2.2.1. Phương pháp Stacking Ensemble trong dự đoán giao thông

Stacking (Stacked Generalization) là một kỹ thuật ensemble learning nâng cao, trong đó nhiều mô hình base learner khác nhau được kết hợp thông qua một meta-learner để cải thiện khả năng dự đoán tổng thể [2]. Kiến trúc stacking đã được chứng minh hiệu quả trong nhiều nghiên cứu về dự đoán giao thông, đặc biệt khi kết hợp các thuật toán tree-based với mạng nơ-ron hồi quy.

Trong nghiên cứu của Cheng et al. (2022), mô hình LightGBM-GRU kết hợp Gated Recurrent Unit (GRU) với LightGBM đã được sử dụng để dự đoán chỉ số ùn tắc giao thông trong ngày làm việc, cho thấy khả năng nắm bắt các đặc trưng phụ thuộc thời gian hiệu quả hơn so với các mô hình đơn lẻ [3]. Tương tự, Lam (2024) so sánh ba mô hình LSTM, Random Forest và XGBoost cho dự đoán lưu lượng xe tại các nút giao thông, kết luận rằng XGBoost đạt hiệu suất tốt nhất về độ chính xác và hiệu quả tính toán [4].

Nghiên cứu của Khan et al. (2022) trên tạp chí Sustainability đã sử dụng Bagging Ensemble kết hợp dữ liệu ô nhiễm không khí để dự đoán lưu lượng giao thông, cho thấy việc tích hợp các nguồn dữ liệu đa dạng giúp cải thiện độ chính xác dự đoán. Bên cạnh đó, Atlantis-press (2023) đề xuất chỉ số ùn tắc mới M_TCI kết hợp mật độ xe với tốc độ, sử dụng XGBoost đạt độ chính xác 90%, vượt trội so với CatBoost, GBM và LightGBM trên cùng tập dữ liệu [5].

### 2.2.2. XGBoost, LightGBM và CatBoost trong dự đoán ùn tắc giao thông

**XGBoost** (Extreme Gradient Boosting) là thuật toán gradient boosting được tối ưu hóa cao, nổi tiếng với khả năng xử lý dữ liệu có cấu trúc quy mô lớn [6]. **LightGBM** (Light Gradient Boosting Machine) sử dụng thuật toán Gradient-based One-Side Sampling (GOSS) và Exclusive Feature Bundling (EFB) cho phép huấn luyện nhanh hơn đáng kể trên dữ liệu chiều cao [7]. **CatBoost** được phát triển bởi Yandex (2017), đặc biệt nổi bật trong việc xử lý các đặc trưng categorical thông qua phương pháp Ordered Target Statistics (OTS), ngăn chặn hiện tượng rò rỉ mục tiêu (target leakage) trong quá trình mã hóa [8].

Theo Cheng et al. (2022), việc kết hợp LightGBM với mạng GRU giúp tăng cường khả năng biểu diễn các đặc trưng có tính tuần tự thời gian trong dữ liệu giao thông, trong khi DAML 2024 chứng minh XGBoost vượt trội hơn LSTM và Random Forest về độ chính xác khi dự đoán lưu lượng xe tại các nút giao thông đô thị [4]. Mô hình hybrid LightGBM-LSTM được đề xuất bởi Archives of Transport (2024) đạt cải thiện 4,87%–47,87% so với các baseline đơn lẻ trên tuyến đường vòng thứ ba của thành phố Chengdu, Trung Quốc [9].

### 2.2.3. Thuật toán Dijkstra và A* trong tìm đường tối ưu đô thị

Bài toán tìm đường đi ngắn nhất (Shortest Path Problem – SPP) là một trong những bài toán cơ bản nhất trong lý thuyết đồ thị, với ứng dụng rộng rãi trong hệ thống giao thông thông minh. Thuật toán **Dijkstra**, được Edsger W. Dijkstra phát triển năm 1956, là thuật toán nền tảng giải bài toán đường đi ngắn nhất từ một đỉnh nguồn đến mọi đỉnh khác trong đồ thị có trọng số không âm, đảm bảo tìm được nghiệm tối ưu [10]. Độ phức tạp thời gian tiêu chuẩn là O(|V|²), được cải thiện thành O(|E| + |V| log|V|) khi sử dụng Fibonacci Heap.

Thuật toán **A*** (A-Star), được Hart et al. (1968) đề xuất, cải thiện hiệu quả của Dijkstra bằng cách bổ sung hàm heuristic h(n) để định hướng tìm kiếm về phía đích, giảm đáng kể số đỉnh cần duyệt [10]. Trong môi trường giao thông thực, nghiên cứu của Feng et al. (2025) trên tạp chí Applied Sciences đã áp dụng A* cải tiến kết hợp với hàm chi phí đa tiêu chí (khoảng cách, điều kiện đường, tình trạng giao thông) cho mạng lưới giao thông công cộng đô thị, đạt kết quả phù hợp cao với Google Maps [11]. Nghiên cứu của Ding et al. (2024) trên tạp chí Engineering Proceedings đề xuất thuật toán Dijkstra phụ thuộc thời gian (Time-Dependent Dijkstra) tính đến độ trễ hàng đợi định kỳ tại các nút giao thông có tín hiệu, giảm 25,36% thời gian di chuyển so với Dijkstra truyền thống trên mạng lưới 15 nút giao thông tại Công nghiệp Viên Tô, Trung Quốc [12].

### 2.2.4. NetworkX cho phân tích mạng lưới giao thông đô thị

**NetworkX** là thư viện Python mã nguồn mở chuyên về phân tích đồ thị và mạng lưới phức tạp. Thư viện cung cấp các thuật toán tìm đường đi ngắn nhất (Dijkstra, Bellman-Ford, Floyd-Warshall) và hỗ trợ đồ thị có hướng, vô hướng, đa đồ thị với các thuộc tính trọng số tùy ý [13]. Khi kết hợp với OSMnx, NetworkX có thể dễ dàng trích xuất dữ liệu mạng lưới đường từ OpenStreetMap để xây dựng đồ thị có thể định tuyến [14].

Theo MDPI Applied Sciences (2025), NetworkX đã được sử dụng để đánh giá các thuật toán đường đi ngắn nhất trên dữ liệu thực tế từ 40 thành phố châu Âu với 120 kết nối, xác nhận rằng việc kết hợp nhiều tiêu chí (khoảng cách, chi phí nhiên liệu, phí cầu đường) qua biểu thức tổ hợp tuyến tính trọng số mang lại kết quả chính xác và có thể triển khai thực tế [13].

### 2.2.5. Tối ưu siêu tham số với Optuna

**Optuna** là framework mã nguồn mở cho tối ưu hóa siêu tham số, sử dụng thuật toán Bayesian Optimization dựa trên Tree-structured Parzen Estimator (TPE) để tìm kiếm hiệu quả trong không gian siêu tham số [15]. Optuna hỗ trợ cắt tỉa (pruning) các thử nghiệm không triển vọng sớm, cho phép huấn luyện song song trên nhiều máy, và tích hợp trực tiếp với các thư viện ML như XGBoost, LightGBM, CatBoost.

Nghiên cứu của Elsevier (2025) áp dụng Optuna để tối ưu siêu tham số cho mô hình LightGBM trong bài toán phân loại thành phần dung môi khí axit, đạt cải thiện 0,4% độ chính xác và giảm hơn 50% thời gian huấn luyện so với tham số mặc định [16]. Kết quả này khẳng định hiệu quả của Optuna trong việc tăng cường hiệu suất gradient boosting trên các bài toán có dữ liệu có cấu trúc phức tạp.

### 2.2.6. BallTree cho truy vấn láng giềng không gian

**BallTree** là cấu trúc dữ liệu phân vùng không gian sử dụng các siêu cầu (hypersphere) lồng nhau để tổ chức các điểm dữ liệu, cho phép truy vấn k láng giềng gần nhất (k-Nearest Neighbors – kNN) với độ phức tạp O(log n) thay vì O(n) như tìm kiếm brute-force [17]. Trong bài toán giao thông, BallTree được sử dụng để trích xuất đặc trưng không gian, ví dụ: xác định các đoạn đường lân cận có tình trạng ùn tắc tương tự, tính toán mật độ đoạn đường trong bán kính cho trước.

Nghiên cứu của Wylot (2024) đã sử dụng BallTree kết hợp dữ liệu POI từ Overture Maps để tạo đặc trưng vùng lân cận cho bài toán đặt trạm sạc xe điện, chứng minh khả năng mở rộng của BallTree cho các ứng dụng không gian quy mô lớn [18]. Ngoài ra, Cai et al. (2016) đề xuất mô hình KNN không-thời gian tương quan (spatiotemporal correlative kNN) cho dự báo nhiều bước ngắn hạn trạng thái giao thông, sử dụng khoảng cách tương đương thay vì khoảng cách vật lý đơn thuần để cải thiện độ chính xác dự đoán [19].

---

# Chương 3. Dữ Liệu Và Phương Pháp Xử Lý

## 3.1. Thu thập dữ liệu

Dữ liệu giao thông TP.HCM được thu thập từ nhiều nguồn bao gồm hệ thống camera giám sát, cảm biến IoT, và dữ liệu GPS từ phương tiện giao thông công cộng. Dataset bao gồm 5 bảng dữ liệu chính gồm:

- **577.967 nút giao thông** (giao lộ, điểm đầu/cuối đoạn đường).
- **84.633 đoạn đường** với các thuộc tính (chiều dài, số làn, loại đường, tốc độ giới hạn).
- **Danh mục các tuyến phố** với cấp đường (cao tốc, quốc lộ, đường đô thị).
- **Trạng thái giao thông** theo thời gian thực.
- **Dữ liệu huấn luyện** với nhãn LOS.

Dữ liệu sau khi thu thập gồm các cột: `_id`, `long`, `lat`, `created_at`, `updated_at`, `s_node_id`, `e_node_id`, `length`, `street_id`, `max_velocity`, `street_level`, `street_name`, `street_type`, `level`, `max_velocity`, `name`, `type`, `updated_at`, `segment_id`, `velocity`, `segment_id`, `date`, `weekday`, `period`, `LOS`, `s_node_id`, `e_node_id`, `length`, `street_id`, `max_velocity`, `street_level`, `street_name`, `street_type`, `long_snode`, `lat_snode`, `long_enode`, `lat_enode`.

**Hình 1.** Trực quan dữ liệu thô sau khi thu thập.

## 3.2. Tiền xử lý dữ liệu

**Hình 2.** Tổng quan quy trình tiền xử lý dữ liệu.

### 3.2.1. Chi tiết quy trình gộp dữ liệu

**Hình 3.** Tổng quan quy trình hợp nhất dữ liệu.

### 3.2.2. Chi tiết quy trình làm sạch dữ liệu

**Hình 4.** Tổng quan quy trình làm sạch dữ liệu.

## 3.3. Trực quan hoá dữ liệu sau khi xử lý

**Hình 5.** Trực quan hoá dữ liệu sau khi xử lý.

Biểu đồ phân bố nhãn LOS cho thấy dữ liệu sau xử lý có tỷ lệ lớp A chiếm cao nhất với 39,7%, phản ánh phần lớn các đoạn đường ở trạng thái thông thoáng. Các lớp còn lại từ B đến F có tỷ lệ thấp hơn và tương đối gần nhau, cho thấy dữ liệu có sự mất cân bằng lớp nhất định.

Biểu đồ phân bố vận tốc theo LOS cho thấy vận tốc có xu hướng giảm dần từ LOS A đến LOS F. Nhóm A có vận tốc trung vị cao nhất, trong khi nhóm F có vận tốc thấp nhất và độ phân tán lớn hơn, phù hợp với ý nghĩa của LOS: từ giao thông thông thoáng đến tắc nghẽn nghiêm trọng.

## 3.4. Xây dựng đặc trưng

Hệ thống trích xuất **149 đặc trưng** từ dữ liệu thô, được phân thành 7 nhóm chính:

| Nhóm đặc trưng | Mô tả |
|----------------|-------|
| **Temporal Features** (Đặc trưng Thời gian) | Mã hóa `hour`, `minute`, `period` dưới dạng `sine/cosine` để giúp mô hình hiểu được tính chu kỳ trong ngày; đồng thời nhận diện ngày nghỉ qua biến `is_weekend`. |
| **Spatial & Infrastructure Features** (Đặc trưng Không gian & Hạ tầng) | Bao gồm mật độ đường (radius density), số làn xe (lanes), giới hạn tốc độ (speed limit) và góc phương vị (degree). |
| **Network Features** (Đặc trưng Mạng lưới) | Thể hiện đặc điểm kết nối của đoạn đường, gồm bậc vào/ra (in_degree, out_degree) và đo lường mức độ giao cắt. |
| **Rolling & Lag Features** (Đặc trưng Độ trễ & Trượt) | Sử dụng vận tốc quá khứ (`velocity_lag_1` đến `12`), trung bình trượt (`rolling_mean`), độ lệch chuẩn (`rolling_std`) và tổng lượng vận tốc để phản ánh xu hướng biến động theo thời gian. |
| **Interaction Features** (Đặc trưng Tương tác) | Tạo các biến kết hợp như tỷ lệ `v_c_ratio` giữa vận tốc và tốc độ tối đa, hoặc năng lực lưu thông tính từ `lane * speed_limit`. |
| **Profile Features** (Đặc trưng Hồ sơ) | Mô tả mức vận tốc trung bình lịch sử của đoạn đường theo từng khoảng thời gian hoặc từng ngày trong tuần. |
| **Neighbor Features** (Đặc trưng Lân cận) | Khai thác độ trễ vận tốc từ các đoạn đường lân cận, còn gọi là đặc trưng trễ không gian – thời gian (Spatio-temporal lag). |

**Bảng 2.** Bảng các nhóm đặc trưng.

**Hình 6.** Trực quan ma trận tương quan đặc trưng mới và LOS sau khi xây dựng đặc trưng.

Ma trận tương quan cho thấy các đặc trưng vận tốc như `velocity_lag_1`, `hist_vel_mean` và `velocity_roll_mean_3` có tương quan âm khá mạnh với `LOS_encoded`, đặc biệt `velocity_roll_mean_3` đạt -0.84. Điều này cho thấy khi vận tốc trung bình hoặc vận tốc gần nhất càng cao thì mức LOS càng thấp, tức giao thông càng thông thoáng.

Ngược lại, `vc_ratio` cũng có tương quan âm với LOS ở mức vừa (-0.44), còn các đặc trưng như `speed_limit_category_enc` và `est_lane_count` có tương quan yếu hơn. Nhìn chung, nhóm đặc trưng liên quan đến vận tốc là yếu tố ảnh hưởng rõ rệt nhất đến mức độ phục vụ giao thông.

## 3.5. Chia tập train/test

| Tập dữ liệu | Số bản ghi | Tỷ lệ | Khoảng thời gian |
|-------------|------------|-------|-----------------|
| Train | 26.752 | 80% | 03/07/2020 – 28/12/2020 |
| Validation | 3.344 | 10% | 28/12/2020 – 15/01/2021 |
| Test | 3.345 | 10% | 15/01/2021 – 22/04/2021 |

**Bảng 3.** Bảng mô tả dữ liệu sau khi chia.

---

# Chương 4. Xây Dựng Mô Hình Dự Báo LOS

## 4.1. Tối ưu siêu tham số

Siêu tham số của XGBoost và LightGBM được tối ưu bằng Optuna với thuật toán TPE (Tree-structured Parzen Estimator), 30 trials cho mỗi base learner. Không gian tìm kiếm bao gồm: `learning_rate` (0,01–0,3), `max_depth` (3–12), `n_estimators` (100–500), `subsample` (0,5–1,0), `colsample_bytree` (0,5–1,0), `min_child_weight` (1–10). Hàm mục tiêu (objective) là Macro F1 score trên tập validation, đảm bảo mô hình hoạt động tốt trên tất cả các cấp LOS — kể cả các lớp thiểu số.

Kết quả sau khi tối ưu:

```python
xgb: {
    'n_estimators': 286,
    'max_depth': 10,
    'learning_rate': 0.09226736960157221,
    'subsample': 0.9929160421700934,
    'colsample_bytree': 0.8143202858702613
}
lgbm: {
    'n_estimators': 242,
    'max_depth': 13,
    'num_leaves': 85,
    'learning_rate': 0.1569949949551549,
    'subsample': 0.6926603011861562
}
```

## 4.2. Kiến trúc mô hình Stacking Ensemble

**Hình 7.** Mô hình Stacking Ensemble.

Mô hình Stacking Ensemble được xây dựng với **2 tầng (level)**:

- **Tầng 1 (Base Learners):** Bốn thuật toán tree-based được huấn luyện độc lập với 3-fold cross-validation trên tập huấn luyện: Random Forest (100 cây), XGBoost (với regularization L1/L2), LightGBM (với GOSS sampling), và CatBoost (với Ordered Target Statistics cho đặc trưng categorical). Mỗi base learner tạo ra một tập predictions OOF (Out-of-Fold) được sử dụng làm đầu vào cho tầng 2.

- **Tầng 2 (Meta-Learner):** Logistic Regression với regularization L2 (Ridge) được sử dụng để kết hợp các predictions từ 4 base learners thành dự đoán cuối cùng. Logistic Regression được chọn vì tính đơn giản, khả năng diễn giải (interpretability), và kháng overfitting khi số lượng base learner nhỏ.

Toàn bộ pipeline tuân thủ nguyên tắc **time-based split**: dữ liệu được chia theo trục thời gian để đảm bảo mô hình không sử dụng thông tin tương lai khi dự đoán quá khứ, phản ánh đúng kịch bản triển khai thực tế.

**Hình 8.** Kết quả đánh giá chéo theo thời gian của mô hình Stacking Ensemble.

## 4.3. Sơ đồ luồng xử lý tìm đường tối ưu dựa trên đồ thị giao thông

**Hình 9.** Sơ đồ luồng xử lý tìm đường tối ưu dựa trên đồ thị giao thông.

---

# Chương 5. Kết Quả Thực Nghiệm Và Đánh Giá

## 5.1. Kết quả dự báo trên tập kiểm thử

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| LOS A | 0.95 | 0.78 | 0.86 | 1038 |
| LOS B | 0.61 | 0.51 | 0.55 | 329 |
| LOS C | 0.42 | 0.74 | 0.54 | 430 |
| LOS D | 0.58 | 0.49 | 0.53 | 301 |
| LOS E | 0.41 | 0.62 | 0.49 | 316 |
| LOS F | 0.91 | 0.71 | 0.80 | 931 |
| **Accuracy** | | | **0.69** | 3345 |
| **Macro Avg** | 0.65 | 0.64 | 0.63 | 3345 |
| **Weighted Avg** | 0.75 | 0.69 | 0.71 | 3345 |

**Bảng 4.** Kết quả dự báo trên tập kiểm thử.

Kết quả đánh giá trên tập kiểm thử cho thấy mô hình đạt accuracy 0,69 và weighted F1-score 0,71. Bên cạnh đó, mô hình đạt Macro ROC-AUC khoảng 0,928 và Micro ROC-AUC khoảng 0,927, cho thấy khả năng phân biệt tổng thể giữa các lớp LOS ở mức tốt. Các lớp LOS A và LOS F có kết quả tốt nhất, với F1-score lần lượt là 0,86 và 0,80, đồng thời ROC-AUC cũng đạt cao, khoảng 0,976 đối với LOS A và 0,970 đối với LOS F. Điều này cho thấy mô hình nhận diện khá tốt hai trạng thái giao thông rõ ràng: thông thoáng và tắc nghẽn nặng.

Tuy nhiên, các lớp trung gian như LOS B, C, D, E có F1-score thấp hơn, dao động khoảng 0,49 – 0,55. Mặc dù ROC-AUC của các lớp này vẫn đạt mức khá, khoảng 0,892 – 0,929, F1-score thấp hơn cho thấy mô hình còn gặp khó khăn trong việc đưa ra nhãn phân loại cuối cùng cho các trạng thái giao thông chuyển tiếp. Nguyên nhân có thể do đặc trưng giữa các lớp trung gian tương đối gần nhau. Nhìn chung, mô hình có khả năng phân biệt xác suất tốt, đặc biệt ở các trạng thái cực trị, nhưng cần cải thiện thêm khả năng phân loại chính xác ở các mức LOS trung gian.

## 5.2. Ma trận nhầm lẫn

**Hình 10.** Ma trận nhầm lẫn.

Ma trận nhầm lẫn cho thấy mô hình dự đoán tốt nhất ở hai lớp LOS A và LOS F. Cụ thể, lớp A có 812/1038 mẫu được dự đoán đúng, còn lớp F có 658/931 mẫu dự đoán đúng. Điều này phù hợp với classification report, cho thấy mô hình nhận diện khá tốt hai trạng thái giao thông rõ ràng: thông thoáng và tắc nghẽn nặng.

Tuy nhiên, mô hình còn nhầm lẫn nhiều ở các lớp trung gian. Lớp B thường bị nhầm sang C với 110 mẫu, lớp D bị nhầm sang C và E, còn lớp F có 185 mẫu bị nhầm sang E. Điều này cho thấy ranh giới giữa các mức LOS liền kề chưa thật sự rõ ràng, đặc biệt ở các trạng thái giao thông chuyển tiếp. Nhìn chung, mô hình dự báo tốt các mức cực trị nhưng cần cải thiện khả năng phân biệt các lớp LOS trung gian.

## 5.3. Biểu đồ Precision-Recall Curve đa lớp

**Hình 11.** Biểu đồ Precision-Recall Curve đa lớp.

Biểu đồ cho thấy mô hình đạt kết quả rất tốt ở hai lớp LOS A và LOS F, với AP lần lượt khoảng 0,96 và 0,93. Điều này chứng tỏ mô hình nhận diện tốt hai trạng thái giao thông rõ ràng là thông thoáng và tắc nghẽn nghiêm trọng.

Các lớp trung gian như LOS B, C, D, E có AP thấp hơn, dao động khoảng 0,52 – 0,63. Trong đó, LOS E có AP thấp nhất khoảng 0,52, cho thấy mô hình còn khó phân biệt các trạng thái giao thông chuyển tiếp. Nhìn chung, mô hình có khả năng dự báo tốt ở các mức LOS cực trị, nhưng cần cải thiện thêm khả năng phân loại ở các mức LOS trung gian.

## 5.4. Phân tích phân bố cấp độ LOS dự báo và độ tin cậy của mô hình

**Hình 12.** Biểu đồ phân tích phân bố cấp độ LOS dự báo và độ tin cậy của mô hình.

Biểu đồ phân bố các cấp độ giao thông LOS do mô hình dự báo trên tập dữ liệu đầu vào. Kết quả cho thấy phần lớn các đoạn đường được dự báo ở mức LOS A với 1.958 đoạn, chiếm tỷ lệ vượt trội so với các lớp còn lại. Điều này cho thấy trong tập dữ liệu dự báo, đa số đoạn đường đang ở trạng thái giao thông thông thoáng. Các mức LOS trung gian như B, C, D, E có số lượng thấp hơn đáng kể, lần lượt là 97, 144, 91 và 112 đoạn. Trong khi đó, lớp LOS F có 274 đoạn, cao hơn các lớp trung gian, phản ánh vẫn tồn tại một số khu vực có nguy cơ ùn tắc nghiêm trọng.

Biểu đồ phân bố độ tin cậy của mô hình khi đưa ra dự báo. Có thể thấy phần lớn giá trị confidence tập trung rất cao, chủ yếu gần mức 0,95 – 1,00. Điều này cho thấy mô hình thường đưa ra dự báo với xác suất tin cậy lớn, đặc biệt đối với các mẫu mà mô hình phân loại rõ ràng. Tuy nhiên, việc phân bố confidence tập trung mạnh gần 1,00 cũng cần được xem xét thận trọng, vì mô hình có thể có xu hướng quá tự tin đối với một số dự đoán.

Nhìn chung, hai biểu đồ cho thấy hệ thống dự báo phần lớn các đoạn đường ở trạng thái thông thoáng, đồng thời mô hình có mức độ tự tin cao khi đưa ra kết quả. Đây là tín hiệu tích cực cho khả năng ứng dụng của hệ thống, tuy nhiên cần tiếp tục kiểm chứng thêm trên dữ liệu thực tế và dữ liệu thời gian thực để đánh giá độ ổn định của mô hình trong nhiều điều kiện giao thông khác nhau.

## 5.5. Những đặc trưng quan trọng mà mô hình học được và tạo ra

**Hình 13.** Những đặc trưng quan trọng mà mô hình học được và tạo ra.

---

# Chương 6. Giao diện hệ thống

## 6.1. Giao diện trang home của hệ thống

**Hình 14, 15.** Giao diện trang home của hệ thống.

## 6.2. Giao diện để người dùng tìm đường đi

**Hình 16, 17.** Giao diện để người dùng tìm đường đi.

Giao diện trên là màn hình Tìm Đường của hệ thống dự báo giao thông TP.HCM. Giao diện cho phép người dùng chọn điểm đi và điểm đến thông qua danh sách gợi ý, ô nhập địa chỉ hoặc click trực tiếp trên bản đồ.

Bên trái là khu vực điều khiển, gồm các ô chọn vị trí, nút đổi điểm đi/điểm đến và nút Tìm đường tối ưu. Bên phải là bản đồ tương tác hiển thị mạng lưới khu vực TP.HCM, hỗ trợ người dùng quan sát vị trí và lựa chọn điểm trực tiếp.

Giao diện cũng hiển thị thông tin tổng quan của đồ thị giao thông như số lượng nút và cạnh. Ngoài ra, hệ thống hỗ trợ chuyển đổi giữa nền sáng và nền tối, giúp tăng khả năng quan sát khi sử dụng trong các điều kiện hiển thị khác nhau.

**Hình 18.** Giao diện để người dùng xem kết quả tìm đường đi.

**Hình 19.** Giao diện để người dùng chọn tuyến đường.

Ngoài ra người dùng có thể chọn các tuyến đường phù hợp.

**Hình 20.** Giao diện để người dùng xem tuyến đường cần đi.

Và bên cạnh trực quan hoá tuyến đường trên map thì hệ thống sẽ liệt kê danh sách các tuyến đường cho người dùng.

---

# Chương 7. Kết Luận Và Hướng Phát Triển

## 7.1. Kết Quả Đạt Được

Đề tài đã xây dựng được hệ thống dự báo mức độ ùn tắc giao thông tại TP.HCM dựa trên chỉ số LOS. Hệ thống thực hiện đầy đủ các bước từ xử lý dữ liệu, xây dựng đặc trưng, huấn luyện mô hình Stacking Ensemble đến đánh giá và triển khai giao diện trực quan. Ngoài chức năng dự báo LOS, hệ thống còn hỗ trợ tìm đường tối ưu trên bản đồ theo các tiêu chí khoảng cách, thời gian và mức độ ùn tắc.

## 7.2. Hạn Chế Của Đề Tài

Dữ liệu sử dụng chủ yếu là dữ liệu đã chuẩn bị sẵn, chưa kết nối trực tiếp với nguồn dữ liệu thời gian thực như camera, GPS hoặc cảm biến giao thông. Mô hình còn nhầm lẫn ở các lớp LOS trung gian như B, C, D và E. Chức năng tìm đường hiện tại vẫn mang tính mô phỏng, chưa cập nhật các sự kiện giao thông thực tế như tai nạn, cấm đường hoặc thời tiết.

## 7.3. Hướng Phát Triển Trong Tương Lai

Trong tương lai, hệ thống có thể tích hợp dữ liệu thời gian thực từ camera, GPS, cảm biến và trung tâm điều hành giao thông. Mô hình cũng có thể được cải tiến bằng các phương pháp học sâu hoặc mô hình học trên đồ thị để khai thác tốt hơn quan hệ không gian - thời gian. Giao diện có thể được mở rộng thành hệ thống web hoàn chỉnh, hỗ trợ nhiều người dùng và cung cấp API cho các ứng dụng khác.

## 7.4. Khả Năng Mở Rộng Vào Hệ Thống ITS Thực Tế

Hệ thống có tiềm năng trở thành một thành phần trong hệ thống giao thông thông minh ITS. Khi được kết nối với dữ liệu thực tế, hệ thống có thể hỗ trợ cảnh báo ùn tắc, đề xuất tuyến đường, điều phối giao thông và hỗ trợ cơ quan quản lý ra quyết định. Đây là nền tảng phù hợp để phát triển các giải pháp giao thông thông minh cho TP.HCM trong tương lai.

---

# Tài Liệu Tham Khảo

[1] Transportation Research Board, *Highway Capacity Manual (HCM 2010)*, 5th ed. Washington, D.C., USA: TRB, 2010. [Liên kết: https://www.civil.iitb.ac.in/tvm/nptel/551_CapLOS/web/web.html]

[2] W. Cheng, J. Li, H. Xiao, and J. Liu, "Combination Predicting Model of Traffic Congestion Index in Weekdays Based on LightGBM-GRU," *Scientific Reports*, vol. 12, no. 1, p. 2912, Feb. 2022. [Liên kết: https://www.nature.com/articles/s41598-022-06975-1]

[3] N. U. Khan, M. A. Shah, C. Maple, E. Ahmed, and N. Asghar, "Traffic Flow Prediction: An Intelligent Scheme for Forecasting Traffic Flow Using Air Pollution Data in Smart Cities with Bagging Ensemble," *Sustainability*, vol. 14, no. 7, p. 4164, Mar. 2022. [Liên kết: https://www.mdpi.com/2073-4441/14/7/4164]

[4] K. N. Lam, "Traffic Prediction Using LSTM, RF and XGBoost," in *Proc. 2nd Int. Conf. Data Anal. Mach. Learn. (DAML)*, vol. 1, SciTePress, 2024, pp. 267–274. [Liên kết: https://www.scitepress.org/PublishedPapers/2024/135156/]

[5] Atlantis-Press, "Improved Road Traffic Congestion Prediction Using Machine Learning through Modified Index," *Atlantis-Press*, 2023. [Liên kết: https://www.atlantis-press.com/article/126011486.pdf]

[6] T. Chen and C. Guestrin, "XGBoost: A Scalable Tree Boosting System," in *Proc. 22nd ACM SIGKDD Int. Conf. Knowl. Discov. Data Min.*, New York, USA, 2016, pp. 785–794. [Liên kết: https://doi.org/10.1145/2939672.2939785]

[7] G. Ke, Q. Meng, T. Finley, T. Wang, W. Chen, W. Ma, Q. Liu, and T. Y. Lin, "LightGBM: The Light Gradient Boosting Machine," in *Proc. Adv. Neural Inf. Process. Syst. (NeurIPS)*, vol. 30, 2017. [Liên kết: https://proceedings.neurips.cc/paper/6907-lightgbm-the-light-gradient-boosting-machine]

[8] A. V. Dorogush, V. Ershelnek, and A. Gulin, "CatBoost: Gradient Boosting with Categorical Features Support," *arXiv:1810.11363*, Oct. 2018. [Liên kết: https://ar5iv.labs.arxiv.org/html/1810.11363]

[9] Archives of Transport, "Urban Road Traffic Congestion Index Prediction Based on a Hybrid LightGBM-LSTM Model," *Archives of Transport*, 2024. [Liên kết: https://archivesoftransport.com/index.php/aot/article/view/822]

[10] P. Muthuvel, G. Pandiyan, S. Manickam, and C. Rajesh, "Optimizing Road Networks: A Graph-Based Analysis with Path-finding and Learning Algorithms," *Int. J. Intell. Transp. Syst. Res.*, vol. 23, pp. 315–329, Apr. 2025. [Liên kết: https://link.springer.com/article/10.1007/s13177-024-00453-w]

[11] Y. Feng, H. Chen, and L. Wang, "Optimal Routing in Urban Road Networks: A Graph-Based Approach Using Dijkstra's Algorithm," *Appl. Sci.*, vol. 15, no. 8, p. 4162, Apr. 2025. [Liên kết: https://www.mdpi.com/2076-3417/15/8/4162]

[12] Z. Ding, S. Wang, J. Liu, and Y. Zhang, "A Time-Dependent Dijkstra's Algorithm for the Shortest Path Considering Periodic Queuing Delays at Signalized Intersections," *Eng. Proc.*, vol. 14, no. 1, p. 61, Jan. 2024. [Liên kết: https://www.mdpi.com/2079-8954/14/1/61]

[13] A. Hagberg, P. J. Schult, and D. A. Swart, "A Contribution of Shortest Paths Algorithms to the NetworkX Python Library," *Appl. Sci.*, vol. 15, no. 15, p. 8273, Jul. 2025. [Liên kết: https://www.mdpi.com/2076-3417/15/15/8273]

[14] G. Boeing, "OSMnx: New Methods for Acquiring, Constructing, Analyzing, and Visualizing Complex Street Networks," *Comput., Environ. Urban Syst.*, vol. 65, pp. 126–139, Sep. 2017. [Liên kết: https://doi.org/10.1016/j.compenvurbsys.2017.05.004]

[15] T. Akiba, S. Sano, T. Yanase, T. Ohta, and M. Koyama, "Optuna: A Next-Generation Hyperparameter Optimization Framework," in *Proc. 25th ACM SIGKDD Int. Conf. Knowl. Discov. Data Min.*, Anchorage, AK, USA, 2019, pp. 2623–2631. [Liên kết: https://dl.acm.org/doi/10.1145/3292500.3330701]

[16] Elsevier, "Optuna-LightGBM: An Optuna Hyperparameter Optimization Framework for the Determination of Solvent Components in Acid Gas Removal Unit Using LightGBM," *Elsevier*, 2025. [Liên kết: https://www.sciencedirect.com/science/article/pii/S2666790825001776]

[17] F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," *J. Mach. Learn. Res.*, vol. 12, pp. 2825–2830, 2011. [Liên kết: https://scikit-learn.org/stable/modules/neighbors.html]

[18] M. Wylot, "Hybrid Scoring System for EV Charger Site Selection with LightGBM and Multi-Dimensional Composite Scoring," 2024. [Liên kết: https://mwylot.net/portfolio/ev-charger-hybrid-scoring/]

[19] Q. Cai, J. Lee, and N. Geroliminis, "A Spatiotemporal Correlative k-Nearest Neighbor Model for Short-Term Traffic Multistep Forecasting," *Transp. Res. Part C: Emerg. Technol.*, vol. 67, pp. 90–111, Jun. 2016. [Liên kết: https://www.sciencedirect.com/science/article/abs/pii/S0968090X15003812]
