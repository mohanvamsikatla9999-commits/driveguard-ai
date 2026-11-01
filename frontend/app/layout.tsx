import type { Metadata } from "next";
import "./style.css";
export const metadata: Metadata={title:"DRIVEGUARD AI | Stay Alert. Stay Alive.",description:"Local-first driver attention monitoring prototype"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
