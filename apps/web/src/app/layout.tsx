import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider, themeScript } from "@/components/ui/theme-provider";
import { ToastProvider } from "@/components/ui/toast";
export const metadata: Metadata = {
  title: "ClipForge — Your best moments, ready to share",
  description: "Turn long videos into thoughtfully framed, captioned clips.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <ThemeProvider>
          <ToastProvider>{children}</ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
