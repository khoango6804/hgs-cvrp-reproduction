# HGS và Set Partitioning ở ngân sách đầy đủ

Gap trung bình của nghiệm tốt nhất qua 10 seed là **0.1015%** với HGS, **0.0955%** với SP từ nghiệm cuối và **0.0955%** với SP thêm nghiệm trung gian. So với SP từ nghiệm cuối, bản mở rộng thắng 0, hòa 8, thua 0 instance.

| Instance | HGS best-of-10 | SP từ nghiệm cuối | SP thêm 2 nghiệm | Δ so với SP cuối (điểm %) |
|---|---:|---:|---:|---:|
| X-n101-k25 | 0.0000% | 0.0000% | 0.0000% | +0.0000 |
| X-n157-k13 | 0.0000% | 0.0000% | 0.0000% | +0.0000 |
| X-n251-k28 | 0.0000% | 0.0000% | 0.0000% | +0.0000 |
| X-n401-k29 | 0.0771% | 0.0771% | 0.0771% | +0.0000 |
| X-n502-k39 | 0.0188% | 0.0058% | 0.0058% | +0.0000 |
| X-n627-k43 | 0.1705% | 0.1641% | 0.1641% | +0.0000 |
| X-n801-k40 | 0.1050% | 0.0982% | 0.0982% | +0.0000 |
| X-n1001-k43 | 0.4409% | 0.4187% | 0.4187% | +0.0000 |
| **Trung bình** | **0.1015%** | **0.0955%** | **0.0955%** | **+0.0000** |

Gap dùng BKS lịch sử năm 2020. Mỗi giá trị dùng nghiệm tốt nhất của 10 seed trên từng instance. Hai nhánh SP dùng cùng các lượt HGS có lưu nghiệm, để đo riêng tác động của mở rộng tập tuyến. Nghiệm trung gian là hai incumbent ngay trước incumbent cuối, hoặc ít hơn nếu seed có ít lần cải thiện.

Mỗi instance có giới hạn `10 × ceil(2,4 × số khách)` giây CPU. Baseline HGS dùng các lượt nguyên bản đã đo trên Ubuntu WSL 2. Nhánh có lưu nghiệm dành 1 giây mỗi seed cho hậu xử lý, và tính chi phí ghi nghiệm trong thời gian HGS. Baseline chạy ở đợt trước và dùng binary không có ghi snapshot. Giới hạn nguyên của CLI có thể vượt nhẹ ở lần kiểm tra thời gian cuối một vòng lặp. Cả pipeline SP mở rộng, kể cả SP từ pool cuối để dự phòng, dùng tổng cộng 3.098 giây CPU trên 8 instance và nằm trong giới hạn của từng instance.

CSV ghi cả cost, CPU thực tế, kích thước pool, và kết quả SP từ nghiệm cuối của đợt đối chứng trước. Các nghiệm đầu vào và đầu ra đều được kiểm tra độc lập về tải trọng, độ phủ và chi phí EUC_2D.

[CSV so sánh](comparison.csv) · [Kết quả từng seed](runs.csv) · [Môi trường Linux](environment.txt)
