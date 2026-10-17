-- Place this source in a Script named BadApplePlayer under ServerScriptService.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local ServerScriptService = game:GetService("ServerScriptService")

local DATA_FOLDER_NAME = "BadAppleData"
local SCREEN_MODULE_NAME = "BadAppleScreen"
local DEBUG_INTERVAL = 1

local function fail(message)
	error("[BadApple] " .. message, 0)
end

local function requireModule(parent, moduleName, description)
	local moduleScript = parent:FindFirstChild(moduleName)
	if not moduleScript then
		fail(string.format("Missing %s ModuleScript '%s' under %s", description, moduleName, parent:GetFullName()))
	end
	if not moduleScript:IsA("ModuleScript") then
		fail(string.format("%s '%s' must be a ModuleScript", description, moduleScript:GetFullName()))
	end

	local ok, result = pcall(require, moduleScript)
	if not ok then
		fail(string.format("Could not load %s '%s': %s", description, moduleName, tostring(result)))
	end
	if type(result) ~= "table" then
		fail(string.format("%s '%s' must return a table", description, moduleName))
	end
	return result
end

local function validateManifest(manifest)
	local requiredPositiveNumbers = {
		{ "width", manifest.width },
		{ "height", manifest.height },
		{ "pixelsPerFrame", manifest.pixelsPerFrame },
		{ "fps", manifest.fps },
		{ "frameCount", manifest.frameCount },
	}
	for _, entry in ipairs(requiredPositiveNumbers) do
		if type(entry[2]) ~= "number" or entry[2] <= 0
			or entry[2] ~= entry[2] or entry[2] == math.huge then
			fail(string.format("Manifest.%s must be a positive number", entry[1]))
		end
	end
	if manifest.width % 1 ~= 0 or manifest.height % 1 ~= 0
		or manifest.pixelsPerFrame % 1 ~= 0 or manifest.frameCount % 1 ~= 0 then
		fail("Manifest dimensions, pixelsPerFrame, and frameCount must be integers")
	end
	if manifest.width * manifest.height ~= manifest.pixelsPerFrame then
		fail(string.format(
			"Manifest pixel count mismatch: width*height is %d, pixelsPerFrame is %d",
			manifest.width * manifest.height,
			manifest.pixelsPerFrame
		))
	end
	if type(manifest.modules) ~= "table" or type(manifest.ranges) ~= "table" then
		fail("Manifest.modules and Manifest.ranges must be tables")
	end
	if #manifest.modules == 0 or #manifest.modules ~= #manifest.ranges then
		fail("Manifest must have matching non-empty modules and ranges lists")
	end
end

local function validatePixels(pixels, moduleName, frameIndex, pixelCount)
	if type(pixels) ~= "table" then
		fail(string.format("%s frame %d must be a pixel array", moduleName, frameIndex))
	end

	for index = 1, pixelCount do
		local value = pixels[index]
		if value ~= 0 and value ~= 1 then
			fail(string.format(
				"%s frame %d has invalid pixel %d (expected 0 or 1)",
				moduleName,
				frameIndex,
				index
			))
		end
	end

	local actualCount = 0
	for index in pairs(pixels) do
		if type(index) ~= "number" or index % 1 ~= 0 or index < 1 or index > pixelCount then
			fail(string.format(
				"%s frame %d has an unexpected pixel key",
				moduleName,
				frameIndex
			))
		end
		actualCount += 1
	end
	if actualCount ~= pixelCount then
		fail(string.format(
			"%s frame %d has %d pixels; expected %d",
			moduleName,
			frameIndex,
			actualCount,
			pixelCount
		))
	end
end

local function loadFrameModules(dataFolder, manifest)
	local loadedModules = {}
	local expectedStart = 0
	local loadedFrameCount = 0

	for moduleIndex, moduleFile in ipairs(manifest.modules) do
		if type(moduleFile) ~= "string" then
			fail(string.format("Manifest.modules[%d] must be a filename", moduleIndex))
		end
		local moduleName = moduleFile:gsub("%.lua$", "")
		local range = manifest.ranges[moduleIndex]
		if type(range) ~= "table" then
			fail(string.format("Manifest.ranges[%d] is missing or invalid", moduleIndex))
		end
		if range.file ~= moduleFile then
			fail(string.format(
				"Manifest range %d filename mismatch: expected '%s', got '%s'",
				moduleIndex,
				moduleFile,
				tostring(range.file)
			))
		end
		if range.startFrame ~= expectedStart or type(range.endFrame) ~= "number"
			or range.endFrame < range.startFrame or range.endFrame % 1 ~= 0 then
			fail(string.format(
				"Invalid frame range for %s: expected start %d, got %s-%s",
				moduleFile,
				expectedStart,
				tostring(range.startFrame),
				tostring(range.endFrame)
			))
		end

		local frames = requireModule(dataFolder, moduleName, "frame data")
		for frameIndex = range.startFrame, range.endFrame do
			local pixels = frames[frameIndex]
			if pixels == nil then
				fail(string.format("%s is missing frame %d", moduleName, frameIndex))
			end
			validatePixels(pixels, moduleName, frameIndex, manifest.pixelsPerFrame)
			loadedFrameCount += 1
		end
		for frameIndex in pairs(frames) do
			if type(frameIndex) ~= "number" or frameIndex % 1 ~= 0
				or frameIndex < range.startFrame or frameIndex > range.endFrame then
				fail(string.format("%s contains an unexpected frame key", moduleName))
			end
		end

		loadedModules[moduleIndex] = {
			startFrame = range.startFrame,
			endFrame = range.endFrame,
			frames = frames,
		}
		expectedStart = range.endFrame + 1
	end

if loadedFrameCount ~= manifest.frameCount
    or expectedStart ~= manifest.frameCount then

    warn("[BadApple] loadedFrameCount =", loadedFrameCount)
    warn("[BadApple] manifest.frameCount =", manifest.frameCount)
    warn("[BadApple] expectedStart =", expectedStart)
    warn("[BadApple] expected value =", manifest.frameCount)

    fail(string.format(
        "Frame count validation failed: loaded=%d, expectedStart=%d, expected=%d",
        loadedFrameCount,
        expectedStart,
        manifest.frameCount
    ))
end

return loadedModules, loadedFrameCount
end

local function getFrame(loadedModules, frameIndex)
	for _, moduleData in ipairs(loadedModules) do
		if frameIndex >= moduleData.startFrame and frameIndex <= moduleData.endFrame then
			return moduleData.frames[frameIndex]
		end
	end
	fail(string.format("No loaded module contains frame %d", frameIndex))
end

local dataFolder = ReplicatedStorage:FindFirstChild(DATA_FOLDER_NAME)
if not dataFolder then
	fail(string.format("Missing folder ReplicatedStorage.%s", DATA_FOLDER_NAME))
end
if not dataFolder:IsA("Folder") then
	fail(string.format("ReplicatedStorage.%s must be a Folder", DATA_FOLDER_NAME))
end

local playbackEvent = ReplicatedStorage:FindFirstChild("BadApplePlayback")
if not playbackEvent then
	fail("Missing RemoteEvent ReplicatedStorage.BadApplePlayback")
end
if not playbackEvent:IsA("RemoteEvent") then
	fail("ReplicatedStorage.BadApplePlayback must be a RemoteEvent")
end

local manifest = requireModule(dataFolder, "Manifest", "manifest")
validateManifest(manifest)

local screenModule = requireModule(ServerScriptService, SCREEN_MODULE_NAME, "screen")
if type(screenModule.new) ~= "function" then
	fail("BadAppleScreen module must return a table with a new(manifest) function")
end

local loadedModules, loadedFrameCount = loadFrameModules(dataFolder, manifest)

print("[BadApple] Creating screen...")
local ok, screenOrError = pcall(function()
    return screenModule.new(manifest)
end)

if not ok then
    error("[BadApple] Screen creation failed: " .. tostring(screenOrError))
end

local screen = screenOrError
print("[BadApple] Screen created successfully!")

local frameDuration = 1 / manifest.fps
local currentFrame = 0
local elapsed = 0
local debugElapsed = 0
local isPlaying = false
local playbackConnection

screen:SetFrame(getFrame(loadedModules, currentFrame))
print(string.format(
	"[BadApple] Ready: loaded=%d frames at %.2f FPS. Waiting for PLAY.",
	loadedFrameCount,
	manifest.fps
))

local function startPlayback()
	if isPlaying then
		return
	end

	isPlaying = true
	print(string.format(
		"[BadApple] Playback started: frame=%d/%d fps=%.2f loaded=%d",
		currentFrame,
		manifest.frameCount,
		manifest.fps,
		loadedFrameCount
	))

	playbackConnection = RunService.Heartbeat:Connect(function(deltaTime)
		elapsed += deltaTime
		debugElapsed += deltaTime

		while elapsed >= frameDuration do
			elapsed -= frameDuration
			currentFrame = (currentFrame + 1) % manifest.frameCount
			screen:SetFrame(getFrame(loadedModules, currentFrame))
		end

		if debugElapsed >= DEBUG_INTERVAL then
			debugElapsed %= DEBUG_INTERVAL
			print(string.format(
				"[BadApple] frame=%d/%d fps=%.2f loaded=%d",
				currentFrame,
				manifest.frameCount,
				manifest.fps,
				loadedFrameCount
			))
		end
	end)
end

playbackEvent.OnServerEvent:Connect(function(player, action)
	if action == "Status" then
		playbackEvent:FireClient(player, if isPlaying then "Started" else "Ready")
		return
	end

	if action ~= "Start" then
		warn(string.format(
			"[BadApple] Ignored unknown playback request from %s",
			player.Name
		))
		return
	end

	if isPlaying then
		playbackEvent:FireClient(player, "Started")
		return
	end

	startPlayback()
	playbackEvent:FireAllClients("Started")
end)
