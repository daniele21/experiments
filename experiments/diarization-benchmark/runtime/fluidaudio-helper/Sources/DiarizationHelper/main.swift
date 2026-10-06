import CoreML
import FluidAudio
import Foundation

struct OutputSegment: Codable {
    let speaker: String
    let start: Double
    let end: Double
}

struct HelperOutput: Codable {
    let engine: String
    let audioDurationSeconds: Double
    let audioPrepareSeconds: Double
    let modelLoadSeconds: Double
    let inferenceSeconds: Double
    let segments: [OutputSegment]
    let metadata: [String: String]

    enum CodingKeys: String, CodingKey {
        case engine
        case audioDurationSeconds = "audio_duration_seconds"
        case audioPrepareSeconds = "audio_prepare_seconds"
        case modelLoadSeconds = "model_load_seconds"
        case inferenceSeconds = "inference_seconds"
        case segments
        case metadata
    }
}

enum ArgumentError: Error, CustomStringConvertible {
    case invalid(String)

    var description: String {
        switch self {
        case .invalid(let message): return message
        }
    }
}

func value(after name: String, in args: [String]) -> String? {
    guard let index = args.firstIndex(of: name), index + 1 < args.count else { return nil }
    return args[index + 1]
}

func computeUnits(named value: String?) -> MLComputeUnits {
    switch value?.lowercased() {
    case "ane": return .cpuAndNeuralEngine
    case "gpu": return .cpuAndGPU
    case "cpu": return .cpuOnly
    default: return .all
    }
}

func sortformerConfig(named value: String?) -> SortformerConfig {
    switch value?.lowercased() {
    case "fast": return .fastV2_1
    case "efficient": return .efficientV2_1
    case "high", "high-context": return .highContextV2_1
    default: return .balancedV2_1
    }
}

func lsVariant(named value: String?) -> LSEENDVariant {
    switch value?.lowercased() {
    case "ami": return .ami
    case "callhome": return .callhome
    case "dihard2": return .dihard2
    default: return .dihard3
    }
}

func lsStep(named value: String?) -> LSEENDStepSize {
    switch value {
    case "100", "100ms": return .step100ms
    case "200", "200ms": return .step200ms
    case "300", "300ms": return .step300ms
    case "400", "400ms": return .step400ms
    default: return .step500ms
    }
}

func timelineSegments(_ timeline: DiarizerTimeline) -> [OutputSegment] {
    var output: [OutputSegment] = []
    for (_, speaker) in timeline.speakers {
        for segment in speaker.finalizedSegments {
            output.append(
                OutputSegment(
                    speaker: "speaker_\(segment.speakerIndex)",
                    start: Double(segment.startTime),
                    end: Double(segment.endTime)
                )
            )
        }
    }
    return output.sorted { lhs, rhs in
        lhs.start == rhs.start ? lhs.speaker < rhs.speaker : lhs.start < rhs.start
    }
}

func runCommunity(audio: [Float]) async throws -> (Double, Double, [OutputSegment], [String: String]) {
    var config = OfflineDiarizerConfig(segmentationStepRatio: 0.1, minSegmentDuration: 0.0)
    config.zeroVoteReembed = OfflineDiarizerConfig.ZeroVoteReembed(
        enabled: true,
        minDurationSeconds: 0.4
    )
    let manager = OfflineDiarizerManager(config: config)
    let loadStart = Date()
    try await manager.prepareModels()
    let loadSeconds = Date().timeIntervalSince(loadStart)

    let inferenceStart = Date()
    let result = try await manager.process(audio: audio)
    let inferenceSeconds = Date().timeIntervalSince(inferenceStart)
    let segments = result.segments.map {
        OutputSegment(
            speaker: String(describing: $0.speakerId),
            start: Double($0.startTimeSeconds),
            end: Double($0.endTimeSeconds)
        )
    }
    return (
        loadSeconds,
        inferenceSeconds,
        segments,
        ["profile": "closedroom-accurate", "pipeline": "community-1-vbx"]
    )
}

func runSortformer(
    audio: [Float],
    configName: String?
) async throws -> (Double, Double, [OutputSegment], [String: String]) {
    let config = sortformerConfig(named: configName)
    let loadStart = Date()
    let models = try await SortformerModels.loadFromHuggingFace(config: config)
    let diarizer = SortformerDiarizer(config: config)
    diarizer.initialize(models: models)
    let loadSeconds = Date().timeIntervalSince(loadStart)

    let inferenceStart = Date()
    let timeline = try diarizer.processComplete(audio, sourceSampleRate: 16_000)
    let inferenceSeconds = Date().timeIntervalSince(inferenceStart)
    return (
        loadSeconds,
        inferenceSeconds,
        timelineSegments(timeline),
        ["config": configName ?? "balanced", "pipeline": "sortformer-v2.1"]
    )
}

func runLSEEND(
    audio: [Float],
    variantName: String?,
    stepName: String?
) async throws -> (Double, Double, [OutputSegment], [String: String]) {
    let variant = lsVariant(named: variantName)
    let step = lsStep(named: stepName)
    let loadStart = Date()
    let model = try await LSEENDModel.loadFromHuggingFace(
        variant: variant,
        stepSize: step,
        computeUnits: .cpuOnly
    )
    let diarizer = try LSEENDDiarizer(model: model)
    let loadSeconds = Date().timeIntervalSince(loadStart)

    let inferenceStart = Date()
    let timeline = try diarizer.processComplete(audio, sourceSampleRate: 16_000)
    let inferenceSeconds = Date().timeIntervalSince(inferenceStart)
    return (
        loadSeconds,
        inferenceSeconds,
        timelineSegments(timeline),
        [
            "variant": variantName ?? "dihard3",
            "step_size": stepName ?? "500",
            "pipeline": "ls-eend"
        ]
    )
}

func runNemotron3(
    audio: [Float],
    variantName: String?,
    threshold: Float,
    units: MLComputeUnits
) async throws -> (Double, Double, [OutputSegment], [String: String]) {
    let name = variantName ?? "fast32"
    guard let config = Nemotron3Config.preset(named: name) else {
        throw ArgumentError.invalid("Unknown Nemotron 3 preset: \(name)")
    }
    let loadStart = Date()
    let models = try await Nemotron3Models.loadFromHuggingFace(
        config: config,
        computeUnits: units
    )
    let diarizer = Nemotron3Diarizer(config: config, models: models)
    let loadSeconds = Date().timeIntervalSince(loadStart)

    let inferenceStart = Date()
    let (probabilities, frameCount) = try diarizer.processComplete(audio)
    let rawSegments = Nemotron3Diarizer.segments(
        probabilities: probabilities,
        frameCount: frameCount,
        threshold: threshold
    )
    let inferenceSeconds = Date().timeIntervalSince(inferenceStart)
    let segments = rawSegments.map {
        OutputSegment(
            speaker: "speaker_\($0.speakerIndex)",
            start: Double($0.startSeconds),
            end: Double($0.endSeconds)
        )
    }
    return (
        loadSeconds,
        inferenceSeconds,
        segments,
        ["variant": name, "threshold": String(threshold), "pipeline": "nemotron-3"]
    )
}

@main
struct DiarizationHelper {
    static func main() async {
        do {
            let args = Array(CommandLine.arguments.dropFirst())
            guard let engine = value(after: "--engine", in: args) else {
                throw ArgumentError.invalid("--engine is required")
            }
            guard let audioPath = value(after: "--audio", in: args) else {
                throw ArgumentError.invalid("--audio is required")
            }

            let prepareStart = Date()
            let audio = try AudioConverter().resampleAudioFile(path: audioPath)
            let prepareSeconds = Date().timeIntervalSince(prepareStart)
            let duration = Double(audio.count) / 16_000.0

            let loadSeconds: Double
            let inferenceSeconds: Double
            let segments: [OutputSegment]
            let metadata: [String: String]

            switch engine {
            case "community1":
                (loadSeconds, inferenceSeconds, segments, metadata) = try await runCommunity(audio: audio)
            case "sortformer":
                (loadSeconds, inferenceSeconds, segments, metadata) = try await runSortformer(
                    audio: audio,
                    configName: value(after: "--config", in: args)
                )
            case "lseend":
                (loadSeconds, inferenceSeconds, segments, metadata) = try await runLSEEND(
                    audio: audio,
                    variantName: value(after: "--variant", in: args),
                    stepName: value(after: "--step-size", in: args)
                )
            case "nemotron3":
                let threshold = Float(value(after: "--threshold", in: args) ?? "0.5") ?? 0.5
                (loadSeconds, inferenceSeconds, segments, metadata) = try await runNemotron3(
                    audio: audio,
                    variantName: value(after: "--variant", in: args),
                    threshold: threshold,
                    units: computeUnits(named: value(after: "--compute-units", in: args))
                )
            default:
                throw ArgumentError.invalid("Unsupported engine: \(engine)")
            }

            let output = HelperOutput(
                engine: engine,
                audioDurationSeconds: duration,
                audioPrepareSeconds: prepareSeconds,
                modelLoadSeconds: loadSeconds,
                inferenceSeconds: inferenceSeconds,
                segments: segments,
                metadata: metadata
            )
            let data = try JSONEncoder().encode(output)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write(Data("\n".utf8))
        } catch {
            FileHandle.standardError.write(Data("\(error)\n".utf8))
            Foundation.exit(1)
        }
    }
}
