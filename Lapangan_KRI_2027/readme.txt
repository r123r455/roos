Ubuntu 24.04 lts
ros jazzy
gazebo harmonic 

Berikut langkah-langkahnya, dari instalasi sampai lapangan tampil.

1. Install Gazebo (sekali saja)

Skrip ini dibuat untuk Gazebo Harmonic (gz sim). Di Ubuntu 22.04 atau 24.04:

sudo apt update
sudo apt install gz-harmonic

Cek apakah sudah terpasang dengan gz sim --version.

2. Taruh file di satu folder

Download lapangan.world dan gen_lapangan.py dari kartu file di atas, lalu simpan di folder yang sama, misalnya ~/gazebo_lapangan/.

3. Jalankan simulasi


cd ~/gazebo_lapangan
gz sim lapangan.world

Jendela Gazebo akan terbuka dan lapangan langsung tampil. Kalau simulasi tampak berhenti, tekan tombol Play (▶) di kiri bawah.

4. Navigasi kamera
(gunakan mouse)
Putar pandangan: klik kiri lalu geser.
Geser kamera: klik tengah (scroll) lalu geser.
Zoom: scroll mouse.

5. Ubah ukuran atau posisi (opsional)

Buka gen_lapangan.py, ubah angka di bagian PARAMETER (misalnya PLAT_H untuk tinggi platform). Lalu buat ulang file world dan jalankan lagi:

bash
python3 gen_lapangan.py
gz sim lapangan.world

6. Memasukkan robot

Dari menu Gazebo, buka Resource Spawner (ikon di pojok kanan atas) dan pilih model robot. Atau tambahkan model Anda sendiri ke lapangan.world dengan tag <include>.

Kalau ada masalah:

Jendela tidak muncul atau macet: coba gz sim -v 4 lapangan.world untuk melihat pesan error.
Perintah gz tidak dikenali: Gazebo belum terpasang, atau Anda memakai Gazebo Classic (gazebo). Untuk Classic, file world perlu disesuaikan seperti catatan sebelumnya.