# pc_motor v1

pc_motor, bilgisayarın **anlık durumunu değil**  
**zaman içindeki davranışını** izleyen bir CLI araçtır.

> “Şu an ne oluyor?” değil  
> **“Neden böyle oldu?”** sorusuna odaklanır.

---

## Ne yapar?
- CPU / RAM / Disk snapshot’ları alır
- Zaman içindeki büyümeyi analiz eder
- CLI üzerinden raporlar üretir

## Ne yapmaz?
- Real-time monitoring değildir
- Agent / daemon çalıştırmaz
- “Her şeyi yapan” bir sistem olmayı hedeflemez

## v1 kapsamı
- disk scan / diff / report
- snapshot history
- golden path yaklaşımı

## Not
Bu proje bilinçli olarak **v1’de durur**.
Bir öğrenme motorudur.
