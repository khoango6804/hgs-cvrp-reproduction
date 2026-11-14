# Kết quả tái lập HGS-CVRP trên Linux

Gap trung bình trên 8 instance là **0.1738%**, so với **0.1637%** của paper trên cùng 8 instance. Chênh lệch là **+0.0101 điểm phần trăm**. Cả 80 lượt đều đạt ngân sách CPU và có nghiệm hợp lệ. Có **3/8** instance đạt BKS lịch sử ở ít nhất một seed.

| Instance | Giây CPU mỗi seed | BKS 2020 | Mean cost Linux | Gap Linux | Gap paper | Δ gap (đpt) | Best Linux | Best paper | Seed đạt BKS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| X-n101-k25 | 240 | 27591 | 27591.0 | 0.0000% | 0.0000% | +0.0000 | 27591 | 27591 | 10/10 |
| X-n157-k13 | 375 | 16876 | 16876.0 | 0.0000% | 0.0000% | +0.0000 | 16876 | 16876 | 10/10 |
| X-n251-k28 | 600 | 38684 | 38691.3 | 0.0189% | 0.0153% | +0.0036 | 38684 | 38684 | 7/10 |
| X-n401-k29 | 960 | 66163 | 66242.5 | 0.1202% | 0.1353% | -0.0151 | 66214 | 66209 | 0/10 |
| X-n502-k39 | 1203 | 69226 | 69249.9 | 0.0345% | 0.0195% | +0.0150 | 69239 | 69230 | 0/10 |
| X-n627-k43 | 1503 | 62164 | 62380.4 | 0.3481% | 0.3340% | +0.0142 | 62270 | 62238 | 0/10 |
| X-n801-k40 | 1920 | 73305 | 73473.1 | 0.2293% | 0.2666% | -0.0372 | 73382 | 73396 | 0/10 |
| X-n1001-k43 | 2400 | 72359 | 72821.7 | 0.6395% | 0.5387% | +0.1007 | 72678 | 72678 | 0/10 |

Gap dùng `100 × (cost − BKS) / BKS` với BKS năm 2020. Gap của paper được tính từ mean cost trong Bảng 2–4 để tránh sai số khi lấy hiệu hai giá trị gap đã làm tròn. Best paper lấy từ Bảng 5–6. Mốc 0,11% của paper là trung bình trên 100 instance. [Bảng thí nghiệm gốc](https://arxiv.org/html/2012.10384#S5)

Mỗi lượt dùng một luồng, seed 1–10 và `-it 20000`. Thời gian là `ceil(2,4 × số khách)` vì CLI của bản phát hành nhận số giây nguyên. Tổng cộng solver dùng 25.559 giờ CPU. Benchmark dùng Ubuntu WSL 2, Core i5-12400F và GCC 15.2. Paper dùng CentOS 7.8, Xeon Gold 6148 và g++ 9.1.0. Tag `v1.0.0` chứa một bản vá nhỏ của tác giả. Seed 1–10 là lựa chọn cho lần tái lập này. [Môi trường chạy](environment.txt) · [Release của tác giả](https://github.com/vidalt/HGS-CVRP/releases/tag/v1.0.0)

Verifier tính lại chi phí EUC_2D từ từng tuyến, kiểm tra khách được phục vụ đúng một lần và tải từng xe. Chi phí cuối trong log hội tụ khớp với nghiệm đã chấm. [Kết quả từng seed](runs.csv) · [Thống kê từng instance](summary.csv)
