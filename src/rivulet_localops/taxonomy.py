from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    code: str
    label: str
    phrases: tuple[str, ...]
    keywords: tuple[str, ...]
    default_target_hours: int = 72


CATEGORIES: tuple[Category, ...] = (
    Category(
        "waste_litter",
        "Waste and litter",
        ("missed collection", "illegal dumping", "overflowing bin", "bin is overflowing", "dumped rubbish"),
        ("bin", "rubbish", "waste", "litter", "garbage", "recycling"),
    ),
    Category(
        "roads_footpaths",
        "Roads and footpaths",
        ("blocked road", "broken footpath", "trip hazard", "road damage"),
        ("pothole", "footpath", "road", "kerb", "pavement", "street"),
    ),
    Category(
        "stormwater_drainage",
        "Stormwater and drainage",
        ("blocked drain", "stormwater drain", "flash flooding", "water over road"),
        ("drain", "stormwater", "flood", "flooding", "culvert"),
    ),
    Category(
        "parks_trees",
        "Parks and trees",
        ("fallen tree", "broken branch", "playground equipment", "tree limb"),
        ("tree", "park", "playground", "branch", "reserve", "grass"),
    ),
    Category(
        "animals",
        "Animal management",
        ("lost dog", "stray dog", "dead animal", "dog attack"),
        ("dog", "cat", "animal", "stray", "barking", "livestock"),
    ),
    Category(
        "parking",
        "Parking",
        ("parking meter", "blocked driveway", "illegal parking"),
        ("parking", "parked", "meter", "car", "vehicle"),
    ),
    Category(
        "facilities",
        "Council facilities",
        ("public toilet", "community hall", "sports ground", "change room"),
        ("toilet", "facility", "library", "hall", "building", "lights"),
    ),
    Category(
        "noise_nuisance",
        "Noise and nuisance",
        ("loud music", "construction noise", "smoke nuisance"),
        ("noise", "noisy", "smoke", "nuisance", "odour", "odor"),
    ),
)

GENERAL_CATEGORY = Category("general_enquiry", "General enquiry", (), (), 120)
