import Foundation

enum Config {
    /// Отдельный инстанс бэкенда для iOS. У Android свой, на 8010.
    static let apiBaseURL = URL(string: "https://proshot-ios.89-221-203-218.sslip.io")!

    /// Идентификаторы совпадают с SKU пакетов на сервере и с товарами
    /// в App Store Connect. Одна строка на три места — маппинг не нужен.
    static let productIDs: [String] = ["pack_basic", "pack_standard", "pack_premium"]
}
