#!/usr/bin/env python3
"""
Обновление всех карточек районов до нового стильного дизайна
"""

def create_district_card(name, slug, description, tag, color_from, color_to, image_url, buildings, price, rating):
    """Создает HTML для стильной карточки района"""
    return f'''            <!-- {name} -->
            <div class="group bg-white rounded-2xl shadow-lg overflow-hidden hover:shadow-2xl transition-all duration-500 transform hover:-translate-y-2 border border-gray-100 district-card" data-district="{slug}">
                <!-- Image Header -->
                <div class="relative h-56 bg-gradient-to-br from-{color_from}-600 to-{color_to}-700 overflow-hidden">
                    <div class="absolute inset-0 bg-cover bg-center opacity-40" style="background-image: url('{image_url}');"></div>
                    
                    <!-- Tag -->
                    <div class="absolute top-4 right-4">
                        <span class="bg-white/20 backdrop-blur-sm text-white px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wide">
                            {tag}
                        </span>
                    </div>
                    
                    <!-- Title Overlay -->
                    <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent p-6">
                        <h3 class="text-2xl font-bold text-white mb-1">{name}</h3>
                        <p class="text-white/90 text-sm">{description}</p>
                    </div>
                </div>
                
                <!-- Content -->
                <div class="p-6">
                    <!-- Stats Grid -->
                    <div class="grid grid-cols-3 gap-4 mb-6">
                        <div class="text-center">
                            <div class="w-12 h-12 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-2">
                                <i class="fas fa-building text-blue-600"></i>
                            </div>
                            <div class="font-bold text-lg text-gray-900">{buildings}</div>
                            <div class="text-xs text-gray-500 uppercase tracking-wide">Новостроек</div>
                        </div>
                        <div class="text-center">
                            <div class="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-2">
                                <i class="fas fa-ruble-sign text-green-600"></i>
                            </div>
                            <div class="font-bold text-lg text-gray-900">{price}k</div>
                            <div class="text-xs text-gray-500 uppercase tracking-wide">₽/м²</div>
                        </div>
                        <div class="text-center">
                            <div class="w-12 h-12 bg-yellow-50 rounded-full flex items-center justify-center mx-auto mb-2">
                                <i class="fas fa-star text-yellow-600"></i>
                            </div>
                            <div class="font-bold text-lg text-gray-900">{rating}</div>
                            <div class="text-xs text-gray-500 uppercase tracking-wide">Рейтинг</div>
                        </div>
                    </div>
                    
                    <!-- Action Button -->
                    <a href="{{{{ url_for('district_detail', district='{slug}') }}}}" 
                       class="block w-full bg-gradient-to-r from-{color_from}-600 to-{color_to}-700 text-white text-center py-3 rounded-xl font-semibold transform transition-all duration-200 hover:from-{color_from}-700 hover:to-{color_to}-800 hover:scale-105 hover:shadow-lg group-hover:shadow-xl">
                        Подробнее о районе
                        <i class="fas fa-arrow-right ml-2 transition-transform group-hover:translate-x-1"></i>
                    </a>
                </div>
            </div>'''

def main():
    """Обновляет все карточки районов"""
    
    # Читаем файл
    with open('templates/districts.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Удаляем старые карточки и заменяем их новыми
    districts_data = [
        # Уже обновлены: Центральный, 40 лет Победы, 9-й километр, Авиагородок
        
        # Аврора
        ('Аврора', 'аврора утренняя заря', 'Уютный жилой микрорайон', 'Уютный', 'pink', 'pink', 
         'https://images.unsplash.com/photo-1566073771259-6a8506099945?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '5', '54', '4.1'),
        
        # Баскет-Холл
        ('Баскет-Холл', 'баскет холл баскетбол спорт', 'Современный спортивный район', 'Спортивный', 'orange', 'orange',
         'https://images.unsplash.com/photo-1574923226119-24e8495ba4ee?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '3', '62', '4.4'),
        
        # Березовый
        ('Березовый', 'березовый береза лес', 'Экологически чистый район', 'Экорайон', 'green', 'green',
         'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '7', '49', '4.2'),
        
        # Западный
        ('Западный', 'западный запад', 'Быстро развивающийся район', 'Перспективный', 'teal', 'teal',
         'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '9', '51', '4.0'),
        
        # Комсомольский
        ('Комсомольский', 'комсомольский молодежный', 'Молодежный активный район', 'Молодежный', 'red', 'red',
         'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '6', '47', '3.9'),
        
        # Прикубанский
        ('Прикубанский', 'прикубанский кубань река', 'Престижный район у реки', 'Престижный', 'cyan', 'cyan',
         'https://images.unsplash.com/photo-1449824913935-59a10b8d2000?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '11', '67', '4.5'),
        
        # Фестивальный
        ('Фестивальный', 'фестивальный фмр праздник', 'Культурный центр города', 'Культурный', 'violet', 'violet',
         'https://images.unsplash.com/photo-1514924013411-cbf25faa35bb?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '18', '68', '5.0'),
        
        # Юбилейный
        ('Юбилейный', 'юбилейный праздничный', 'Торжественный микрорайон', 'Торжественный', 'amber', 'amber',
         'https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80',
         '4', '53', '4.0')
    ]
    
    print("🎨 Генерирую новые стильные карточки районов...")
    
    # Создаем HTML для всех карточек
    new_cards = []
    
    for district_data in districts_data:
        card_html = create_district_card(*district_data)
        new_cards.append(card_html)
    
    print(f"✅ Создано {len(new_cards)} новых карточек")
    print("\n🔧 Теперь нужно вручную заменить старые карточки в шаблоне")
    print("\n📋 Список карточек для замены:")
    for i, (name, _, _, _, _, _, _, _, _, _) in enumerate(districts_data):
        print(f"  {i+1}. {name}")
    
    # Сохраняем карточки в отдельные файлы для удобства
    for i, card in enumerate(new_cards):
        district_name = districts_data[i][0]
        with open(f'card_{i+1}_{district_name.lower().replace(" ", "_").replace("-", "_")}.html', 'w', encoding='utf-8') as f:
            f.write(card)
    
    print(f"\n✅ Карточки сохранены в отдельные файлы для удобства замены")

if __name__ == "__main__":
    main()