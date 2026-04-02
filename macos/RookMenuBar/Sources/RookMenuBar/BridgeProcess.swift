import Foundation

struct BridgeEnvelope: Decodable {
    var type: String
    var state: String?
    var status: String?
    var text: String?
    var role: String?
    var pending: Bool?
    var level: Double?
    var bars: [Double]?
    var target: String?
    var mode: String?
    var message: String?
    var voice_configured: Bool?
    var openclaw_configured: Bool?
    var ok: Bool?
    var command: String?
}

enum BridgeCommand {
    case ping
    case sendText(String)
    case startListening
    case stopListening
    case hardStopVoice
    case setMode(String)
    case snapshot
    case shutdown

    var payload: [String: Any] {
        switch self {
        case .ping:
            return ["type": "ping"]
        case let .sendText(text):
            return ["type": "send_text", "text": text]
        case .startListening:
            return ["type": "start_listening"]
        case .stopListening:
            return ["type": "stop_listening"]
        case .hardStopVoice:
            return ["type": "hard_stop_voice"]
        case let .setMode(mode):
            return ["type": "set_mode", "mode": mode]
        case .snapshot:
            return ["type": "snapshot"]
        case .shutdown:
            return ["type": "shutdown"]
        }
    }
}

final class BridgeProcess: @unchecked Sendable {
    var onEvent: ((BridgeEnvelope) -> Void)?
    var onTermination: ((String) -> Void)?

    private let decoder = JSONDecoder()
    private var process: Process?
    private var stdinHandle: FileHandle?
    private var stdoutBuffer = Data()
    private var stderrBuffer = Data()

    func start() throws {
        if process != nil {
            return
        }

        let repoRoot = try Self.locateRepoRoot()
        let launch = Self.resolvePythonLaunch(in: repoRoot)

        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        let stdinPipe = Pipe()

        process.currentDirectoryURL = repoRoot
        process.executableURL = launch.executableURL
        process.arguments = launch.arguments + ["-m", "rook.macos.backend"]
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe
        process.standardInput = stdinPipe

        stdoutPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            self?.consumeStdout(handle.availableData)
        }

        stderrPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            self?.consumeStderr(handle.availableData)
        }

        process.terminationHandler = { [weak self] task in
            let callback = self?.onTermination
            DispatchQueue.main.async {
                callback?("Backend terminated with code \(task.terminationStatus).")
            }
        }

        try process.run()
        self.process = process
        self.stdinHandle = stdinPipe.fileHandleForWriting
    }

    func stop() {
        send(.shutdown)
        stdinHandle?.closeFile()
        process?.terminate()
        process = nil
        stdinHandle = nil
    }

    func send(_ command: BridgeCommand) {
        guard let stdinHandle else {
            return
        }

        guard JSONSerialization.isValidJSONObject(command.payload),
              let data = try? JSONSerialization.data(withJSONObject: command.payload)
        else {
            return
        }

        var line = data
        line.append(0x0A)
        try? stdinHandle.write(contentsOf: line)
    }

    private func consumeStdout(_ data: Data) {
        guard !data.isEmpty else {
            return
        }

        stdoutBuffer.append(data)
        emitBufferedLines(from: &stdoutBuffer, handler: handleStdoutLine)
    }

    private func consumeStderr(_ data: Data) {
        guard !data.isEmpty else {
            return
        }

        stderrBuffer.append(data)
        emitBufferedLines(from: &stderrBuffer) { [weak self] line in
            let callback = self?.onTermination
            DispatchQueue.main.async {
                callback?(line)
            }
        }
    }

    private func emitBufferedLines(from buffer: inout Data, handler: (String) -> Void) {
        while let newlineIndex = buffer.firstIndex(of: 0x0A) {
            let lineData = buffer[..<newlineIndex]
            buffer.removeSubrange(...newlineIndex)
            guard let line = String(data: lineData, encoding: .utf8), !line.isEmpty else {
                continue
            }
            handler(line)
        }
    }

    private func handleStdoutLine(_ line: String) {
        guard let data = line.data(using: .utf8),
              let envelope = try? decoder.decode(BridgeEnvelope.self, from: data)
        else {
            let callback = self.onTermination
            DispatchQueue.main.async {
                callback?("Could not decode backend event: \(line)")
            }
            return
        }

        let callback = self.onEvent
        DispatchQueue.main.async {
            callback?(envelope)
        }
    }

    private static func locateRepoRoot() throws -> URL {
        if let override = ProcessInfo.processInfo.environment["ROOK_REPO_ROOT"] {
            return URL(fileURLWithPath: override, isDirectory: true)
        }

        var current = URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true)
        while true {
            let candidate = current.appendingPathComponent("pyproject.toml")
            if FileManager.default.fileExists(atPath: candidate.path) {
                return current
            }

            let parent = current.deletingLastPathComponent()
            if parent.path == current.path {
                throw NSError(
                    domain: "RookMenuBar",
                    code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Could not locate the rook-agent repo root."]
                )
            }
            current = parent
        }
    }

    private static func resolvePythonLaunch(in repoRoot: URL) -> (executableURL: URL, arguments: [String]) {
        let venvPython = repoRoot.appendingPathComponent(".venv/bin/python")
        if FileManager.default.isExecutableFile(atPath: venvPython.path) {
            return (venvPython, [])
        }
        return (URL(fileURLWithPath: "/usr/bin/env"), ["python3"])
    }
}
