import { Inter } from "next/font/google";
import "./globals.css";

// Inter stands in for Linear's proprietary display/text faces (DESIGN (2).md, "Note on Font Substitutes")
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = { title: "Job Tracker" };

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
