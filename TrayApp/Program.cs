using System;
using System.Drawing;
using System.Drawing.Text;
using System.Windows.Forms;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Threading;

namespace TrayApp
{
    static class Program
    {
        private static NotifyIcon trayIcon;
        private static double glucoseValue = 5.0; // Default value
        private static HttpClient httpClient;
        private static Timer updateTimer;
        private static SynchronizationContext uiContext;
        private static bool isInRedZone = false;
        private static DateTime? lastWarningTime = null;
        
        private const string ApiEndpoint = "https://firestore.googleapis.com/v1/projects/gluco-watch/databases/(default)/documents/users/78347/";
        private const double LOW_THRESHOLD = 3.9;
        private const double HIGH_THRESHOLD = 10.0;

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // Capture UI thread context
            uiContext = SynchronizationContext.Current ?? new WindowsFormsSynchronizationContext();

            httpClient = new HttpClient();

            trayIcon = new NotifyIcon();
            trayIcon.Visible = true;
            trayIcon.Text = "Glucose Monitor";

            // Initial icon
            trayIcon.Icon = CreateGlucoseIcon(glucoseValue);

            // Context menu
            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Items.Add("Exit", null, (s, e) => Application.Exit());
            trayIcon.ContextMenuStrip = menu;

            // Set up timer to fetch data every 1 minute
            updateTimer = new Timer();
            updateTimer.Interval = 60000; // 1 minute in milliseconds
            updateTimer.Tick += async (s, e) => await FetchGlucoseData();
            updateTimer.Start();

            // Fetch immediately on startup
            _ = Task.Run(async () => await FetchGlucoseData());

            Application.Run();
        }

        static async Task FetchGlucoseData()
        {
            try
            {
                HttpResponseMessage response = await httpClient.GetAsync(ApiEndpoint);
                response.EnsureSuccessStatusCode();

                string jsonContent = await response.Content.ReadAsStringAsync();
                var jsonDoc = JsonDocument.Parse(jsonContent);

                // Navigate to fields.main.mapValue.fields.glucose.doubleValue
                if (jsonDoc.RootElement.TryGetProperty("fields", out var fields) &&
                    fields.TryGetProperty("main", out var main) &&
                    main.TryGetProperty("mapValue", out var mapValue) &&
                    mapValue.TryGetProperty("fields", out var mainFields) &&
                    mainFields.TryGetProperty("glucose", out var glucose) &&
                    glucose.TryGetProperty("doubleValue", out var doubleValue))
                {
                    double glucoseDouble = doubleValue.GetDouble();

                    // Update icon on UI thread
                    if (trayIcon != null && uiContext != null)
                    {
                        uiContext.Post(_ =>
                        {
                            bool wasInRedZone = isInRedZone;
                            bool nowInRedZone = glucoseDouble < LOW_THRESHOLD;
                            
                            glucoseValue = glucoseDouble;
                            trayIcon.Icon?.Dispose();
                            trayIcon.Icon = CreateGlucoseIcon(glucoseValue);
                            trayIcon.Text = $"Glucose: {glucoseValue:F1}";
                            
                            // Handle red zone warnings
                            if (nowInRedZone)
                            {
                                // Just entered red zone
                                if (!wasInRedZone)
                                {
                                    isInRedZone = true;
                                    lastWarningTime = DateTime.Now;
                                    ShowRedZoneWarning(glucoseDouble);
                                }
                                // Still in red zone - check if we should show warning again
                                else if (lastWarningTime.HasValue)
                                {
                                    TimeSpan timeSinceLastWarning = DateTime.Now - lastWarningTime.Value;
                                    if (timeSinceLastWarning.TotalMinutes >= 1)
                                    {
                                        lastWarningTime = DateTime.Now;
                                        ShowRedZoneWarning(glucoseDouble);
                                    }
                                }
                            }
                            else
                            {
                                // Left red zone - reset tracking
                                if (wasInRedZone)
                                {
                                    isInRedZone = false;
                                    lastWarningTime = null;
                                }
                            }
                        }, null);
                    }
                }
            }
            catch (Exception ex)
            {
                // On error, keep showing the last known value
                // Could optionally show an error icon or log the error
                System.Diagnostics.Debug.WriteLine($"Error fetching glucose data: {ex.Message}");
            }
        }

        static Icon CreateGlucoseIcon(double value)
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
                    // Round to nearest integer for display in small icon
                    string text = Math.Round(value).ToString();
                    SizeF size = g.MeasureString(text, font);

                    float x = (16 - size.Width) / 2;
                    float y = (16 - size.Height) / 2 - 1;

                    g.DrawString(text, font, textBrush, x, y);
                }
            }

            return Icon.FromHandle(bmp.GetHicon());
        }

        static void ShowRedZoneWarning(double value)
        {
            if (trayIcon != null)
            {
                trayIcon.BalloonTipTitle = "Glucose Warning";
                trayIcon.BalloonTipText = $"Your glucose is now at {value:F1} level";
                trayIcon.BalloonTipIcon = ToolTipIcon.Warning;
                trayIcon.ShowBalloonTip(5000); // Show for 5 seconds
            }
        }

        static Color GetGlucoseColor(double value)
        {
            if (value < LOW_THRESHOLD)
                return Color.Red;        // Low
            if (value > HIGH_THRESHOLD)
                return Color.Orange;     // High
            return Color.Green;          // Normal (LOW_THRESHOLD to HIGH_THRESHOLD)
        }
    }
}
