import os
import sys
import time
from playwright.sync_api import sync_playwright

def run_tests():
    # Pastikan cache bersih sebelum mulai agar skenario token palsu benar-benar memicu request jaringan
    cache_dir = os.path.join(os.path.dirname(__file__), ".cache")
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(cache_dir, f))

    test_results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        print("Navigasi ke http://localhost:8501 ...")
        page.goto("http://localhost:8501", wait_until="networkidle")
        page.wait_for_timeout(3000)

        sidebar = page.locator('[data-testid="stSidebar"]')

        # =========================================================================
        # Skenario Negatif 1:
        # Pilih API Renewables.ninja, token KOSONG -> klik tombol 'Ambil Data Radiasi'
        # -> assert muncul error 'API Token Renewables.ninja diperlukan.'
        # =========================================================================
        try:
            print("\n[RUNNING] Skenario Negatif 1...")
            # Pilih radio "API Renewables.ninja"
            radio_ninja = sidebar.locator('label:has-text("API Renewables.ninja")')
            radio_ninja.click()
            page.wait_for_timeout(1000)

            # Pastikan field token kosong
            token_input = sidebar.locator('input[type="password"]')
            token_input.fill("")
            page.wait_for_timeout(500)

            # Klik "Ambil Data Radiasi"
            btn_fetch = sidebar.locator('button:has-text("Ambil Data Radiasi")')
            btn_fetch.click()
            page.wait_for_timeout(1500)

            # Assert error message
            alert = sidebar.locator('[data-testid="stAlert"]')
            alert_text = alert.first.inner_text().strip() if alert.count() > 0 else ""
            print("  Alert Negatif 1:", alert_text)

            assert "Token API Renewables.ninja diperlukan" in alert_text or "Renewables.ninja diperlukan" in alert_text
            test_results.append({
                "scenario": "Skenario Negatif 1: API Renewables.ninja, token KOSONG",
                "status": "PASS",
                "detail": f"Pesan error terdeteksi sesuai ekspektasi: '{alert_text}'"
            })
        except Exception as e:
            test_results.append({
                "scenario": "Skenario Negatif 1: API Renewables.ninja, token KOSONG",
                "status": "FAIL",
                "detail": str(e)
            })

        # =========================================================================
        # Skenario Negatif 2:
        # Masukkan token palsu/ngawur 'token_palsu_123' -> klik 'Ambil Data Radiasi'
        # -> assert muncul error 'Gagal mengambil data'.
        # =========================================================================
        try:
            print("\n[RUNNING] Skenario Negatif 2...")
            token_input = sidebar.locator('input[type="password"]')
            token_input.fill("token_palsu_123")
            page.wait_for_timeout(500)

            # Klik "Ambil Data Radiasi"
            btn_fetch = sidebar.locator('button:has-text("Ambil Data Radiasi")')
            btn_fetch.click()

            # Tunggu respon API gagal
            page.wait_for_timeout(5000)
            alerts = sidebar.locator('[data-testid="stAlert"]').all_inner_texts()
            alert_text = " ".join(alerts).strip()
            print("  Alert Negatif 2:", alert_text)

            assert "Gagal mengambil data" in alert_text
            test_results.append({
                "scenario": "Skenario Negatif 2: Token palsu 'token_palsu_123'",
                "status": "PASS",
                "detail": f"Pesan error API terdeteksi: '{alert_text}'"
            })
        except Exception as e:
            test_results.append({
                "scenario": "Skenario Negatif 2: Token palsu 'token_palsu_123'",
                "status": "FAIL",
                "detail": str(e)
            })

        # =========================================================================
        # Skenario Positif 1:
        # Masukkan token valid '985481250cd3ff9fb0123d0c943a648506f512a9', pilih Kupang
        # -> klik 'Ambil Data Radiasi' -> assert muncul sukses 'Data radiasi berhasil diperbarui.'.
        # =========================================================================
        try:
            print("\n[RUNNING] Skenario Positif 1...")
            VALID_TOKEN = "985481250cd3ff9fb0123d0c943a648506f512a9"
            token_input = sidebar.locator('input[type="password"]')
            token_input.fill(VALID_TOKEN)
            page.wait_for_timeout(500)

            # Verifikasi / pilih lokasi Kupang
            loc_box = sidebar.locator('[data-testid="stSelectbox"]:has-text("Lokasi Referensi")')
            # Cek jika belum Kupang, klik dan pilih Kupang
            if "Kupang" not in loc_box.inner_text():
                loc_box.click()
                page.wait_for_timeout(500)
                page.locator('[role="option"]:has-text("Kupang")').click()
                page.wait_for_timeout(500)

            # Klik "Ambil Data Radiasi"
            btn_fetch = sidebar.locator('button:has-text("Ambil Data Radiasi")')
            btn_fetch.click()

            # Tunggu indikator sukses
            page.wait_for_timeout(7000)
            alerts = sidebar.locator('[data-testid="stAlert"]').all_inner_texts()
            alert_text = " ".join(alerts).strip()
            print("  Alert Positif 1:", alert_text)

            assert "Data radiasi berhasil diperbarui." in alert_text
            test_results.append({
                "scenario": "Skenario Positif 1: Token valid & Lokasi Kupang",
                "status": "PASS",
                "detail": f"Pesan sukses terdeteksi: '{alert_text}'"
            })
        except Exception as e:
            test_results.append({
                "scenario": "Skenario Positif 1: Token valid & Lokasi Kupang",
                "status": "FAIL",
                "detail": str(e)
            })

        # =========================================================================
        # Skenario Positif 2:
        # Topologi On-Grid, klik 'Kalkulasi Sizing & Kinerja'
        # -> assert ringkasan metrik tampil (Kapasitas Terpasang, Rasio DC/AC, Self Consumption)
        # -> verifikasi grafik plotly ter-render
        # -> verifikasi tidak ada traceback Python di halaman.
        # =========================================================================
        try:
            print("\n[RUNNING] Skenario Positif 2...")
            # Pastikan topologi On-Grid
            topo_box = sidebar.locator('[data-testid="stSelectbox"]:has-text("Topologi Sistem")')
            if "On-Grid" not in topo_box.inner_text():
                topo_box.click()
                page.wait_for_timeout(500)
                page.locator('[role="option"]:has-text("On-Grid")').click()
                page.wait_for_timeout(500)

            btn_calc = page.locator('button:has-text("Kalkulasi Sizing & Kinerja")')
            btn_calc.scroll_into_view_if_needed()
            btn_calc.click()
            page.wait_for_timeout(4000)

            # Assert metrik
            metrics = page.locator('[data-testid="stMetric"]').all()
            metric_data = {}
            for m in metrics:
                lbl = m.locator('[data-testid="stMetricLabel"]').inner_text().strip()
                val = m.locator('[data-testid="stMetricValue"]').inner_text().strip()
                metric_data[lbl] = val

            print("  Metrik terdeteksi:", metric_data)

            assert any("KAPASITAS TERPASANG" in k.upper() for k in metric_data), "Kapasitas Terpasang tidak ditemukan"
            assert any("RASIO DC" in k.upper() for k in metric_data), "Rasio DC/AC tidak ditemukan"
            assert any("SELF CONSUMPTION" in k.upper() for k in metric_data), "Self Consumption tidak ditemukan"

            # Assert Plotly chart
            plotly_count = page.locator('.js-plotly-plot').count()
            print("  Plotly chart count:", plotly_count)
            assert plotly_count >= 1, "Grafik Plotly tidak ter-render"

            # Assert tidak ada traceback Python
            body_text = page.locator('body').inner_text()
            assert "Traceback (most recent call last)" not in body_text, "Traceback Python terdeteksi di halaman"

            cap_val = next(v for k, v in metric_data.items() if "KAPASITAS TERPASANG" in k.upper())
            ratio_val = next(v for k, v in metric_data.items() if "RASIO DC" in k.upper())
            sc_val = next(v for k, v in metric_data.items() if "SELF CONSUMPTION" in k.upper())

            test_results.append({
                "scenario": "Skenario Positif 2: Topologi On-Grid, Kalkulasi Sizing & Kinerja",
                "status": "PASS",
                "detail": f"Metrik valid (Kapasitas: {cap_val}, Rasio DC/AC: {ratio_val}, Self-Consumption: {sc_val}), {plotly_count} Plotly chart tampil, bebas traceback."
            })
        except Exception as e:
            test_results.append({
                "scenario": "Skenario Positif 2: Topologi On-Grid, Kalkulasi Sizing & Kinerja",
                "status": "FAIL",
                "detail": str(e)
            })

        # =========================================================================
        # Skenario Positif 3:
        # Coba topologi Hybrid/Off-Grid -> verifikasi opsi baterai muncul dan kalkulasi tetap jalan lancar.
        # =========================================================================
        try:
            print("\n[RUNNING] Skenario Positif 3...")
            # 1. Topologi Hybrid
            topo_box = sidebar.locator('[data-testid="stSelectbox"]:has-text("Topologi Sistem")')
            topo_box.click()
            page.wait_for_timeout(500)
            page.locator('[role="option"]:has-text("Hybrid")').click()
            page.wait_for_timeout(1000)

            # Cek opsi baterai di form
            battery_section = page.locator('text=Penyimpanan Energi (Bank Baterai)')
            assert battery_section.count() > 0, "Opsi Penyimpanan Energi (Bank Baterai) tidak muncul pada topologi Hybrid"

            btn_calc = page.locator('button:has-text("Kalkulasi Sizing & Kinerja")')
            btn_calc.scroll_into_view_if_needed()
            btn_calc.click()
            page.wait_for_timeout(4000)

            # Verifikasi metrik baterai muncul
            metrics_hybrid = page.locator('[data-testid="stMetric"]').all()
            hybrid_data = {
                m.locator('[data-testid="stMetricLabel"]').inner_text().strip(): m.locator('[data-testid="stMetricValue"]').inner_text().strip()
                for m in metrics_hybrid
            }
            print("  Metrik Hybrid:", hybrid_data)
            assert any("BATERAI" in k.upper() for k in hybrid_data), "Metrik baterai tidak tampil pada Hybrid"

            # Verifikasi grafik SOC baterai muncul (Plotly charts count should increase or be present)
            plotly_count_hybrid = page.locator('.js-plotly-plot').count()
            print("  Plotly count Hybrid:", plotly_count_hybrid)
            assert plotly_count_hybrid >= 2, "Grafik alur daya dan SOC baterai diharapkan minimal 2 grafik"

            # 2. Topologi Off-Grid
            topo_box = sidebar.locator('[data-testid="stSelectbox"]:has-text("Topologi Sistem")')
            topo_box.click()
            page.wait_for_timeout(500)
            page.locator('[role="option"]:has-text("Off-Grid")').click()
            page.wait_for_timeout(1000)

            assert page.locator('text=Penyimpanan Energi (Bank Baterai)').count() > 0, "Opsi baterai tidak muncul pada Off-Grid"

            btn_calc = page.locator('button:has-text("Kalkulasi Sizing & Kinerja")')
            btn_calc.scroll_into_view_if_needed()
            btn_calc.click()
            page.wait_for_timeout(4000)

            body_offgrid = page.locator('body').inner_text()
            assert "Traceback (most recent call last)" not in body_offgrid, "Traceback terdeteksi pada Off-Grid"

            test_results.append({
                "scenario": "Skenario Positif 3: Topologi Hybrid & Off-Grid (Penyimpanan Baterai)",
                "status": "PASS",
                "detail": f"Opsi baterai tampil interaktif, metrik baterai terisi ({hybrid_data.get('KAPASITAS BANK BATERAI', 'Aktif')}), 2 grafik Plotly (alur daya + SOC) ter-render, kalkulasi Off-Grid & Hybrid sukses bebas error."
            })
        except Exception as e:
            test_results.append({
                "scenario": "Skenario Positif 3: Topologi Hybrid & Off-Grid (Penyimpanan Baterai)",
                "status": "FAIL",
                "detail": str(e)
            })

        browser.close()

    return test_results

if __name__ == "__main__":
    results = run_tests()
    print("\n" + "="*70)
    print("HASIL PENGUJIAN E2E BROWSER (PLAYWRIGHT / CHROMIUM)")
    print("="*70)
    all_passed = True
    for r in results:
        status_marker = "PASS" if r["status"] == "PASS" else "FAIL"
        print(f"[{status_marker}] {r['scenario']}")
        print(f"       Observasi: {r['detail']}")
        if r["status"] != "PASS":
            all_passed = False
    print("="*70)
    sys.exit(0 if all_passed else 1)
