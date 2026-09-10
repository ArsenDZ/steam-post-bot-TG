export const metadata = {
  title: 'Steam Post Bot',
  description: 'Генератор постов о раздачах игр',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body style={{ fontFamily: 'system-ui, sans-serif', margin: 0, padding: 0 }}>
        <div style={{ minHeight: '100vh', background: '#fafafa', paddingBottom: '50px' }}>
          {children}
        </div>
      </body>
    </html>
  )
}
