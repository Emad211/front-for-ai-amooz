'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const FeatureCard = ({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) => (
    <Card className="bg-card/50 border-border backdrop-blur-sm text-center transform transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10">
        <CardHeader className="items-center">
            <div className="bg-primary/10 text-primary p-4 rounded-full mb-4 ring-2 ring-primary/20">
                {icon}
            </div>
            <CardTitle className="text-xl font-bold text-text-light">{title}</CardTitle>
        </CardHeader>
        <CardContent>
            <p className="text-text-muted text-sm leading-7">{description}</p>
        </CardContent>
    </Card>
);
