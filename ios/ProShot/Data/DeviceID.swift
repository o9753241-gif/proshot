import Foundation
import UIKit

/// Идентификатор установки для заголовка `X-Device-Id`.
///
/// На Android это случайный UUID в DataStore: он исчезает при удалении
/// приложения. `identifierForVendor` ведёт себя так же — обнуляется, когда
/// с устройства удалены все приложения этого разработчика. Поэтому лимит
/// «15 генераций в час» работает на обеих платформах одинаково.
///
/// UUID в Keychain пережил бы переустановку и сделал лимит строже, чем на
/// Android. Это меняло бы продуктовое правило, поэтому так не сделано.
enum DeviceID {
    static var current: String {
        UIDevice.current.identifierForVendor?.uuidString
            ?? fallback
    }

    /// Крайне редкий случай: система не отдала идентификатор. Тогда свой,
    /// сохранённый до перезапуска, — лучше, чем новый на каждый запрос.
    private static let fallback: String = {
        let key = "proshot.device.fallback"
        if let saved = UserDefaults.standard.string(forKey: key) { return saved }
        let fresh = UUID().uuidString
        UserDefaults.standard.set(fresh, forKey: key)
        return fresh
    }()
}
