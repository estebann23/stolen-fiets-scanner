import type { Metadata } from "next"
import { Inter } from "next/font/google"

import { Providers } from "@/components/providers"
import { SceneBackdrop } from "@/components/scene-backdrop"
import { SiteHeader } from "@/components/site-header"

import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
})

export const metadata: Metadata = {
  title: "Stolen Bike Matcher",
  description:
    "Compare a stolen-bike report with second-hand listings. Results are candidates for police review — not accusations.",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col font-sans antialiased">
        <SceneBackdrop />
        <Providers>
          <SiteHeader />
          <main className="relative z-10 flex-1">{children}</main>
        </Providers>
      </body>
    </html>
  )
}
