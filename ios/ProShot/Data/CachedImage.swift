import SwiftUI

/// Картинка из сети с кэшем в памяти.
///
/// Зачем своя вместо AsyncImage: тот не кэширует ничего. При прокрутке списка
/// сцен он запрашивает один и тот же файл заново и отменяет незавершённые
/// загрузки — в журнале сервера было видно по три обращения к одному и тому же
/// превью подряд, а на экране карточки оставались пустыми.
///
/// Кэш общий на приложение и живёт в памяти: сцены пересматривают по многу раз
/// за сеанс, а на диск класть незачем — файлы небольшие и меняются редко.
@MainActor
final class ImageCache {
    static let shared = ImageCache()

    private let cache: NSCache<NSURL, UIImage> = {
        let c = NSCache<NSURL, UIImage>()
        c.countLimit = 120          // сцен в категории заметно меньше
        c.totalCostLimit = 64 << 20 // 64 МБ
        return c
    }()

    /// Идущие загрузки: два показа одной картинки ждут один запрос, а не два.
    private var inFlight: [URL: Task<UIImage?, Never>] = [:]

    func image(for url: URL) -> UIImage? {
        cache.object(forKey: url as NSURL)
    }

    func load(_ url: URL) async -> UIImage? {
        if let ready = image(for: url) { return ready }
        if let running = inFlight[url] { return await running.value }

        let task = Task<UIImage?, Never> { [weak self] in
            defer { Task { @MainActor in self?.inFlight[url] = nil } }
            guard let (data, _) = try? await URLSession.shared.data(from: url),
                  let image = UIImage(data: data) else { return nil }
            await MainActor.run {
                self?.cache.setObject(image, forKey: url as NSURL,
                                      cost: data.count)
            }
            return image
        }
        inFlight[url] = task
        return await task.value
    }
}

/// Замена AsyncImage: то же назначение, но с кэшем.
struct CachedImage<Placeholder: View>: View {
    let url: URL?
    @ViewBuilder var placeholder: () -> Placeholder

    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).resizable()
            } else {
                placeholder()
            }
        }
        .task(id: url) {
            guard let url else { return }
            if let ready = ImageCache.shared.image(for: url) {
                image = ready
                return
            }
            image = await ImageCache.shared.load(url)
        }
    }
}
