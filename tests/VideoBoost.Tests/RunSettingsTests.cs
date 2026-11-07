using VideoBoost.Engine;

namespace VideoBoost.Tests;

/// <summary>Проверки override-семантики RunSettings и legacy-резолверов.</summary>
public sealed class RunSettingsTests
{
    [Fact]
    public void Resolve_BalancedWithoutOverrides_ReturnsPresetDefaults()
    {
        var resolved = new RunSettings().Resolve(PresetKind.Balanced);

        Assert.Equal(PresetKind.Balanced, resolved.Preset);
        Assert.Equal("Баланс", resolved.PresetTitle);
        Assert.Equal(PresetDefaults.Balanced.Description, resolved.PresetDescription);
        Assert.Equal(ScaleMode.X2, resolved.Scale);
        Assert.Equal(ModelMode.Light, resolved.Model);
        Assert.True(resolved.Interpolate);
        Assert.Equal(FpsMode.Fps60, resolved.Fps);
        Assert.Equal(ContentKind.General, resolved.Content);
        Assert.Equal(EncoderMode.AmfHevc, resolved.Encoder);
        Assert.Equal(QualityMode.Balanced, resolved.Quality);
        Assert.Equal(TileMode.T384, resolved.Tile);
        Assert.True(resolved.SaveSpace);
        Assert.True(resolved.TileFromPreset);
        Assert.Equal(60, resolved.TargetFps);
        Assert.Equal(2, resolved.ResolveScale(1080));
        Assert.Equal(384, resolved.ResolveTile(2));
        Assert.Equal(ModelNames.Light, resolved.ResolveModel(2));
        Assert.Equal((22, 21), resolved.GetQualityLevels());
    }

    [Fact]
    public void Resolve_DefaultPreset_IsBalanced()
    {
        var resolved = new RunSettings().Resolve();

        Assert.Equal(PresetKind.Balanced, resolved.Preset);
        Assert.Equal(EncoderMode.AmfHevc, resolved.Encoder);
    }

    [Fact]
    public void Resolve_OverridesWinOverPreset()
    {
        var settings = new RunSettings(
            Preset: PresetKind.Balanced,
            Scale: ScaleMode.X4,
            Model: ModelMode.Heavy,
            Interpolate: false,
            Fps: FpsMode.Fps120,
            Content: ContentKind.Anime,
            Encoder: EncoderMode.Cpu,
            Quality: QualityMode.Speed,
            Tile: TileMode.T512,
            SaveSpace: false);

        var resolved = settings.Resolve();

        Assert.Equal(ScaleMode.X4, resolved.Scale);
        Assert.Equal(ModelMode.Heavy, resolved.Model);
        Assert.False(resolved.Interpolate);
        Assert.Equal(FpsMode.Fps120, resolved.Fps);
        Assert.Equal(120, resolved.TargetFps);
        Assert.Equal(ContentKind.Anime, resolved.Content);
        Assert.Equal(EncoderMode.Cpu, resolved.Encoder);
        Assert.Equal(QualityMode.Speed, resolved.Quality);
        Assert.Equal(TileMode.T512, resolved.Tile);
        Assert.False(resolved.SaveSpace);
        Assert.False(resolved.TileFromPreset);
        Assert.Equal((26, 23), resolved.GetQualityLevels());
    }

    [Fact]
    public void Resolve_AutoEncoderAndQuality_TakePresetValues()
    {
        var resolved = new RunSettings(
                Encoder: EncoderMode.Auto,
                Quality: QualityMode.Auto)
            .Resolve(PresetKind.Max);

        Assert.Equal(EncoderMode.AmfHevc, resolved.Encoder);
        Assert.Equal(QualityMode.Max, resolved.Quality);
        Assert.Equal((19, 18), resolved.GetQualityLevels());
    }

    [Theory]
    [InlineData(ScaleMode.X2, 1080, 2)]
    [InlineData(ScaleMode.X3, 1080, 3)]
    [InlineData(ScaleMode.X4, 1080, 4)]
    [InlineData(ScaleMode.Auto2160, 1080, 2)]
    [InlineData(ScaleMode.Auto2160, 720, 3)]
    [InlineData(ScaleMode.Auto2160, 540, 4)]
    [InlineData(ScaleMode.Auto2160, 2160, 1)]
    [InlineData(ScaleMode.Auto2160, 0, 2)]
    [InlineData(ScaleMode.Auto4320, 1080, 4)]
    [InlineData(ScaleMode.Auto4320, 2160, 2)]
    [InlineData(ScaleMode.Auto4320, 4320, 1)]
    public void ResolveScale_MatchesLegacyAutoRules(ScaleMode mode, int sourceHeight, int expected)
    {
        var resolved = new RunSettings(Preset: PresetKind.Balanced, Scale: mode).Resolve();

        Assert.Equal(expected, resolved.ResolveScale(sourceHeight));
    }

    [Theory]
    [InlineData(PresetKind.Fast, null, ContentKind.General, 2, ModelNames.Light)]
    [InlineData(PresetKind.Balanced, null, ContentKind.General, 2, ModelNames.Light)]
    [InlineData(PresetKind.Max, null, ContentKind.General, 4, ModelNames.Heavy)]
    [InlineData(PresetKind.Max, null, ContentKind.Anime, 4, ModelNames.HeavyAnime)]
    [InlineData(PresetKind.Max, null, ContentKind.General, 2, ModelNames.Light)]
    [InlineData(PresetKind.Balanced, ModelMode.Heavy, ContentKind.General, 4, ModelNames.Heavy)]
    [InlineData(PresetKind.Balanced, ModelMode.Auto, ContentKind.General, 4, ModelNames.Light)]
    [InlineData(PresetKind.Max, ModelMode.Auto, ContentKind.Anime, 4, ModelNames.HeavyAnime)]
    [InlineData(PresetKind.Max, ModelMode.Light, ContentKind.General, 4, ModelNames.Light)]
    public void ResolveModel_MatchesLegacyHeavyOnlyAtX4(
        PresetKind preset,
        ModelMode? model,
        ContentKind content,
        int scale,
        string expected)
    {
        var resolved = new RunSettings(
                Preset: preset,
                Model: model,
                Content: content)
            .Resolve();

        Assert.Equal(expected, resolved.ResolveModel(scale));
    }

    [Theory]
    [InlineData(PresetKind.Fast, null, 2, 256)]
    [InlineData(PresetKind.Fast, null, 3, 384)]
    [InlineData(PresetKind.Fast, null, 4, 384)]
    [InlineData(PresetKind.Balanced, null, 4, 384)]
    [InlineData(PresetKind.Max, null, 4, 512)]
    [InlineData(PresetKind.Fast, TileMode.Auto, 4, 384)]
    [InlineData(PresetKind.Fast, TileMode.T256, 4, 256)]
    [InlineData(PresetKind.Max, TileMode.T384, 4, 384)]
    public void ResolveTile_MatchesLegacyPresetBumpAndExplicitMode(
        PresetKind preset,
        TileMode? tile,
        int scale,
        int expected)
    {
        var resolved = new RunSettings(Preset: preset, Tile: tile).Resolve();

        Assert.Equal(expected, resolved.ResolveTile(scale));
    }

    [Theory]
    [InlineData(QualityMode.Speed, 26, 23)]
    [InlineData(QualityMode.Balanced, 22, 21)]
    [InlineData(QualityMode.Max, 19, 18)]
    [InlineData(QualityMode.Auto, 22, 21)]
    public void QualityLevels_MatchLegacyTable(QualityMode quality, int qp, int crf)
    {
        Assert.Equal((qp, crf), QualityLevels.For(quality));
    }
}
