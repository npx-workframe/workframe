# Mobile

iOS and Android surface.

This slot is optional and should usually use Expo / React Native when native mobile matters.

Mobile should consume `apps/api` through typed contracts or SDK clients. Do not copy backend authorization logic into the client. The client may optimize visibility; the backend remains authoritative.
