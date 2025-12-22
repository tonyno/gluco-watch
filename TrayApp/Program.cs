using System;
using System.Drawing;
using System.Drawing.Text;
using System.Windows.Forms;

namespace TrayApp
{
    static class Program
    {
        private static NotifyIcon trayIcon;
        private static int glucoseValue = 105; // SAMPLE VALUE

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            trayIcon = new NotifyIcon();
            trayIcon.Visible = true;
            trayIcon.Text = "Glucose Monitor";

            trayIcon.Icon = CreateGlucoseIcon(glucoseValue);

            // Context menu
            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Items.Add("Exit", null, (s, e) => Application.Exit());
            trayIcon.ContextMenuStrip = menu;

            Application.Run();
        }

        static Icon CreateGlucoseIcon(int value)
        {
            Color bgColor = GetGlucoseColor(value);

            Bitmap bmp = new Bitmap(16, 16);
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.Clear(bgColor);
                g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

                using (Font font = new Font("Segoe UI", 8, FontStyle.Bold, GraphicsUnit.Pixel))
                using (Brush textBrush = Brushes.White)
                {
                    string text = value.ToString();
                    SizeF size = g.MeasureString(text, font);

                    float x = (16 - size.Width) / 2;
                    float y = (16 - size.Height) / 2 - 1;

                    g.DrawString(text, font, textBrush, x, y);
                }
            }

            return Icon.FromHandle(bmp.GetHicon());
        }

        static Color GetGlucoseColor(int value)
        {
            if (value < 70)
                return Color.Red;        // Low
            if (value <= 140)
                return Color.Green;      // Normal
            return Color.Orange;         // High
        }
    }
}
