'use client';

import Link from 'next/link';
import { Contact, LogOut, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
} from '@/components/ui/dropdown-menu';

interface UserProfileProps {
  user?: {
    name: string;
    email: string;
    avatar?: string;
  };
}

export function UserProfile({ user = {
  name: 'علیرضا رضایی',
  email: 'ali.rezaei@example.com',
  avatar: 'https://picsum.photos/seed/user/100/100'
} }: UserProfileProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full">
          <Avatar className="h-10 w-10">
            <AvatarImage
              src={user.avatar}
              alt={user.name}
            />
            <AvatarFallback>{user.name.substring(0, 2)}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1 text-right">
            <p className="text-sm font-medium leading-none">{user.name}</p>
            <p className="text-xs leading-none text-muted-foreground">
              {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem asChild className="justify-end">
            <Link href="/profile" className="flex items-center w-full">
              <span className="flex-1 text-right">پروفایل</span>
              <User className="mr-2 h-4 w-4" />
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem className="justify-end">
            <span className="flex-1 text-right">پشتیبانی</span>
            <Contact className="mr-2 h-4 w-4" />
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="justify-end">
           <Link href="/login" className="flex items-center w-full text-destructive">
            <span className="flex-1 text-right">خروج</span>
            <LogOut className="mr-2 h-4 w-4" />
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
