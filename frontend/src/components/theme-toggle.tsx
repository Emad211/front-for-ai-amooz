"use client"

import * as React from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const toggleTheme = () => {
    setTheme(theme === "light" ? "dark" : "light")
  }

  return (
    <button onClick={toggleTheme} className="flex items-center w-full">
      {theme === 'light' ? <Moon className="ml-2 h-4 w-4" /> : <Sun className="ml-2 h-4 w-4" />}
      <span>{theme === 'light' ? 'حالت تاریک' : 'حالت روشن'}</span>
    </button>
  )
}
