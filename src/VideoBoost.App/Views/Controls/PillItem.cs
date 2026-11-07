using Microsoft.UI.Xaml;

namespace VideoBoost.App.Views.Controls;

/// <summary>
/// Элемент пилюльного выбора: заголовок и необязательная подпись.
/// Один и тот же тип используют и компактные чипы (32 px), и пресеты (48 px).
/// </summary>
public sealed class PillItem
{
    /// <summary>Создаёт элемент выбора.</summary>
    /// <param name="text">Заголовок пилюли.</param>
    /// <param name="caption">Подпись под заголовком (для пресетов); пустая — скрыта.</param>
    public PillItem(string text, string caption = "")
    {
        Text = text;
        Caption = caption;
    }

    /// <summary>Заголовок пилюли.</summary>
    public string Text { get; }

    /// <summary>Подпись под заголовком (для пресетов).</summary>
    public string Caption { get; }

    /// <summary>Видимость подписи: без подписи строка не занимает место в чипе.</summary>
    public Visibility CaptionVisibility =>
        string.IsNullOrWhiteSpace(Caption) ? Visibility.Collapsed : Visibility.Visible;

    /// <summary>
    /// Минимальная высота контента: у пресета с подписью 40 px (+ padding 4/4 = 48),
    /// у обычного чипа 0 (высоту задаёт MinHeight 32 у PillItemStyle).
    /// </summary>
    public double MinContentHeight => string.IsNullOrWhiteSpace(Caption) ? 0 : 40;
}
