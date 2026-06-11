import Foundation

protocol SingBoxRunner {
    func start(configData: Data) throws
    func stop()
}

final class MissingSingBoxRunner: SingBoxRunner {
    func start(configData: Data) throws {
        throw MissingSingBoxRuntimeError()
    }

    func stop() {}
}

struct MissingSingBoxRuntimeError: Error {}

