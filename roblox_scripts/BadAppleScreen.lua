-- Place this source in a ModuleScript named BadAppleScreen.
local Workspace = game:GetService("Workspace")

local MODEL_NAME = "BadAppleScreen"
local PIXEL_SIZE = 1
local PIXEL_GAP = 0.05
local SCREEN_CFRAME = CFrame.new(0, 20, 0)

local BLACK = Color3.fromRGB(0, 0, 0)
local WHITE = Color3.fromRGB(255, 255, 255)

local BadAppleScreen = {}
BadAppleScreen.__index = BadAppleScreen

local function getOrCreateModel()
	local existing = Workspace:FindFirstChild(MODEL_NAME)
	if existing then
		assert(existing:IsA("Model"), "Workspace.BadAppleScreen exists but is not a Model")
		return existing
	end

	local model = Instance.new("Model")
	model.Name = MODEL_NAME
	model.Parent = Workspace
	return model
end

local function configurePart(part, name, size, cframe, parent)
	part.Name = name
	part.Size = size
	part.CFrame = cframe
	part.Anchored = true
	part.CanCollide = false
	part.CanTouch = false
	part.CanQuery = false
	part.CastShadow = false
	part.Material = Enum.Material.SmoothPlastic
	part.Parent = parent
end

function BadAppleScreen.new(manifest, options)
	options = options or {}

	local width = manifest.width
	local height = manifest.height
	local pixelCount = manifest.pixelsPerFrame
	local pixelSize = options.pixelSize or PIXEL_SIZE
	local gap = options.gap
	if gap == nil then
		gap = PIXEL_GAP
	end
	local screenCFrame = options.cframe or SCREEN_CFRAME

	assert(type(pixelSize) == "number" and pixelSize > 0, "pixelSize must be positive")
	assert(type(gap) == "number" and gap >= 0, "gap must be non-negative")

	local model = getOrCreateModel()
	local pixelsByName = {}
	for _, child in ipairs(model:GetChildren()) do
		if child.Name:match("^Pixel_%d+$") then
			if child:IsA("BasePart") and pixelsByName[child.Name] == nil then
				pixelsByName[child.Name] = child
			else
				child:Destroy()
			end
		end
	end

	local parts = table.create(pixelCount)
	local pitch = pixelSize + gap
	for index = 1, pixelCount do
		local name = string.format("Pixel_%04d", index)
		local part = pixelsByName[name]
		if not part then
			part = Instance.new("Part")
		end

		local row = math.floor((index - 1) / width) + 1
		local column = ((index - 1) % width) + 1
		local x = (column - (width + 1) / 2) * pitch
		local y = ((height + 1) / 2 - row) * pitch
		local localCFrame = CFrame.new(x, y, 0)
		configurePart(
			part,
			name,
			Vector3.new(pixelSize, pixelSize, pixelSize),
			screenCFrame * localCFrame,
			model
		)
		parts[index] = part
	end

	for name, part in pairs(pixelsByName) do
		local index = tonumber(name:match("^Pixel_(%d+)$"))
		if index == nil or index > pixelCount then
			part:Destroy()
		end
	end

	return setmetatable({
		model = model,
		parts = parts,
		lastPixels = table.create(pixelCount),
		pixelCount = pixelCount,
	}, BadAppleScreen)
end

function BadAppleScreen:SetFrame(pixels)
	for index = 1, self.pixelCount do
		local value = pixels[index]
		if value ~= self.lastPixels[index] then
			self.parts[index].Color = if value == 1 then WHITE else BLACK
			self.lastPixels[index] = value
		end
	end
end

return BadAppleScreen
