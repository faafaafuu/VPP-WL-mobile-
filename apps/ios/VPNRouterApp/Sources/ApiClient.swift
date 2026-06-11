import Foundation

enum ApiError: Error {
    case missingToken
    case httpStatus(Int, Data)
}

final class ApiClient {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func fetchConfig(accessToken: String) async throws -> Data {
        var request = URLRequest(url: baseURL.appendingPathComponent("/api/config"))
        request.httpMethod = "GET"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        let (data, response) = try await session.data(for: request)
        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(statusCode) else {
            throw ApiError.httpStatus(statusCode, data)
        }
        return data
    }
}

extension ApiError {
    var allowsConfigFallback: Bool {
        if case let .httpStatus(statusCode, _) = self {
            return statusCode == 503 || statusCode >= 500
        }
        return false
    }
}

