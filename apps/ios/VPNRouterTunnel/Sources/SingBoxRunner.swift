import Foundation

protocol SingBoxRunner {
    func start(configJson: String) throws
    func stop()
}

final class MissingSingBoxRunner: SingBoxRunner {
    func start(configJson: String) throws {
        throw MissingSingBoxRuntimeError()
    }

    func stop() {}
}

struct MissingSingBoxRuntimeError: Error {}
