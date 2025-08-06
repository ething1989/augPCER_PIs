import numpy as np
import operator
import os
import tflite_runtime.interpreter as tflite

userDir = os.path.expanduser('~')
labels_file = "labels"

pantanal_birds = {
    "Alder Flycatcher",
    "Amazonian Motmot",
    "Amazonian Pygmy-Owl",
    "American Golden-Plover",
    "American Kestrel",
    "Ash-colored Cuckoo",
    "Azure Gallinule",
    "Band-tailed Nighthawk",
    "Bank Swallow",
    "Bar-breasted Piculet",
    "Bare-faced Curassow",
    "Bare-faced Ibis",
    "Barn Owl",
    "Barn Swallow",
    "Barred Forest-Falcon",
    "Bat Falcon",
    "Bearded Tachuri",
    "Black Hawk-Eagle",
    "Black Skimmer",
    "Black Vulture",
    "Black-and-white Hawk-Eagle",
    "Black-bellied Whistling-Duck",
    "Black-capped Antwren",
    "Black-crowned Night-Heron",
    "Black-fronted Nunbird",
    "Black-tailed Trogon",
    "Black-throated Antbird",
    "Black-winged Stilt",
    "Blackish Rail",
    "Blacksmith Thrush",
    "Blue Dacnis",
    "Blue Ground Dove",
    "Blue-crowned Trogon",
    "Blue-headed Parrot",
    "Bran-colored Flycatcher",
    "Brown-crested Flycatcher",
    "Buff-cheeked Greenlet",
    "Campo Flicker",
    "Cattle Egret",
    "Chaco Chachalaca",
    "Chestnut Seedeater",
    "Chestnut-eared Aracari",
    "Chivi Vireo",
    "Chotoy Spinetail",
    "Cinereous-breasted Spinetail",
    "Cinnamon-throated Hermit",
    "Collared Forest-Falcon",
    "Collared Plover",
    "Common Gallinule",
    "Common Nighthawk",
    "Common Pauraque",
    "Common Scale-backed Antbird",
    "Connecticut Warbler",
    "Copper Seedeater",
    "Crane Hawk",
    "Crested Eagle",
    "Double-toothed Kite",
    "Dull-colored Grassquit",
    "Dusky-capped Flycatcher",
    "Eared Dove",
    "East Amazonian Fire-eye",
    "Fork-tailed Palm-Swift",
    "Gilded Hummingbird",
    "Glittering-bellied Emerald",
    "Gray Tinamou",
    "Gray-breasted Crake",
    "Gray-breasted Martin",
    "Gray-breasted Sabrewing",
    "Gray-cowled Wood-Rail",
    "Gray-fronted Dove",
    "Gray-headed Kite",
    "Great Egret",
    "Great Tinamou",
    "Greater Ani",
    "Green Ibis",
    "Green-and-rufous Kingfisher",
    "Green-backed Becard",
    "Green-backed Trogon",
    "Green-barred Woodpecker",
    "Green-cheeked Parakeet",
    "Guira Cuckoo",
    "Harpy Eagle",
    "Helmeted Manakin",
    "Hooded Siskin",
    "Hook-billed Kite",
    "House Sparrow",
    "Large-billed Tern",
    "Laughing Falcon",
    "Least Grebe",
    "Lesser Nighthawk",
    "Lesser Yellowlegs",
    "Lettered Aracari",
    "Little Nightjar",
    "Long-tailed Tyrant",
    "Long-winged Harrier",
    "Marbled Wood-Quail",
    "Marsh Seedeater",
    "Masked Tityra",
    "Masked Yellowthroat",
    "Mississippi Kite",
    "Mouse-colored Tyrannulet",
    "Nacunda Nighthawk",
    "Neotropic Cormorant",
    "Ocellated Crake",
    "Ochre-cheeked Spinetail",
    "Olivaceous Woodcreeper",
    "Osprey",
    "Pale-bellied Mourner",
    "Pale-bellied Tyrant-Manakin",
    "Pale-legged Hornero",
    "Pale-vented Pigeon",
    "Peach-fronted Parakeet",
    "Pearl Kite",
    "Pearly-breasted Cuckoo",
    "Pheasant Cuckoo",
    "Picazuro Pigeon",
    "Picui Ground Dove",
    "Pied-billed Grebe",
    "Piratic Flycatcher",
    "Plain-breasted Ground Dove",
    "Plain-brown Woodcreeper",
    "Planalto Hermit",
    "Plumbeous Kite",
    "Purple Martin",
    "Razor-billed Curassow",
    "Red-eyed Vireo",
    "Red-throated Caracara",
    "Red-throated Piping-Guan",
    "Red-winged Tinamou",
    "Reddish Hermit",
    "Ringed Kingfisher",
    "Roseate Spoonbill",
    "Ruby-topaz Hummingbird",
    "Ruddy Ground Dove",
    "Ruddy Pigeon",
    "Ruddy Quail-Dove",
    "Rufous Casiornis",
    "Rufous Hornero",
    "Rufous-breasted Hermit",
    "Rufous-breasted Leaftosser",
    "Rufous-capped Nunlet",
    "Rufous-crowned Pygmy-Tyrant",
    "Rufous-faced Crake",
    "Rufous-fronted Thornbird",
    "Rufous-sided Crake",
    "Rufous-tailed Jacamar",
    "Rufous-thighed Kite",
    "Russet-mantled Foliage-gleaner",
    "Rusty-margined Guan",
    "Saffron-billed Sparrow",
    "Scaled Dove",
    "Scaled Pigeon",
    "Scaly-headed Parrot",
    "Scissor-tailed Nightjar",
    "Short-tailed Nighthawk",
    "Sick's Swift",
    "Small-billed Elaenia",
    "Small-billed Tinamou",
    "Snail Kite",
    "Snowy Egret",
    "Solitary Black Cacique",
    "Solitary Sandpiper",
    "Southern Lapwing",
    "Spectacled Owl",
    "Spectacled Tyrant",
    "Spot-backed Puffbird",
    "Spot-tailed Nightjar",
    "Spot-winged Pigeon",
    "Spotted Nothura",
    "Striped Cuckoo",
    "Striped Owl",
    "Suiriri Flycatcher",
    "Sunbittern",
    "Sungrebe",
    "Swainson's Flycatcher",
    "Swallow-tailed Hummingbird",
    "Swallow-tailed Kite",
    "Swallow-winged Puffbird",
    "Tawny-bellied Screech-Owl",
    "Toco Toucan",
    "Tropical Pewee",
    "Tropical Screech-Owl",
    "Turquoise-fronted Parrot",
    "Ultramarine Grosbeak",
    "Undulated Tinamou",
    "Vermilion Flycatcher",
    "Wattled Jacana",
    "Whistling Heron",
    "White Hawk",
    "White Woodpecker",
    "White-bearded Hermit",
    "White-chinned Sapphire",
    "White-collared Swift",
    "White-crested Elaenia",
    "White-crested Tyrannulet",
    "White-eared Puffbird",
    "White-eyed Parakeet",
    "White-faced Whistling-Duck",
    "White-fringed Antwren",
    "White-fronted Nunbird",
    "White-fronted Woodpecker",
    "White-lored Spinetail",
    "White-naped Xenopsaris",
    "White-necked Puffbird",
    "White-necked Thrush",
    "White-striped Warbler",
    "White-tailed Hawk",
    "White-tailed Kite",
    "White-throated Spadebill",
    "White-tipped Dove",
    "White-vented Violetear",
    "White-wedged Piculet",
    "Wood Stork",
    "Yellow-bellied Elaenia",
    "Yellow-bellied Seedeater",
    "Yellow-billed Cuckoo",
    "Yellow-billed Tern",
    "Yellow-collared Macaw",
    "Yellow-headed Caracara",
    "Yellow-olive Flycatcher",
    "Yellow-rumped Cacique",
    "Yellow-tufted Woodpecker",
    "Yellowish Pipit",
}

class Model:
    def __init__(self, model, threads=2):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.model_path = os.path.join(base_dir, model + ".tflite")
        print(f'Model path: {self.model_path}')

        self.myinterpreter = tflite.Interpreter(model_path=self.model_path, num_threads=threads)
        self.myinterpreter.allocate_tensors()
        input_details = self.myinterpreter.get_input_details()
        output_details = self.myinterpreter.get_output_details()
        self.INPUT_LAYER_INDEX = input_details[0]['index']
        self.INPUT_SHAPE = input_details[0]['shape']
        self.OUTPUT_LAYER_INDEX = output_details[0]['index']

        # Load labels
        self.CLASSES = []
        labelspath = os.path.join(base_dir, labels_file + ".txt")
        with open(labelspath, 'r') as lfile:
            for line in lfile:
                _, common_name = line.strip().split('_', 1)
                self.CLASSES.append(common_name)

        print('Model loaded successfully.')

    def custom_sigmoid(self, x, sensitivity=1.0):
        return 1.0 / (1.0 + np.exp(-sensitivity * x))

    def preprocess_sample(self, sample):
        # Ensure the sample matches the expected input shape of the model
        return np.array(sample, dtype='float32').reshape(self.INPUT_SHAPE)

    def predict(self, sample, sensitivity=1.0, threshold=0.1):
        try:
            processed_sample = self.preprocess_sample(sample)
            self.myinterpreter.set_tensor(self.INPUT_LAYER_INDEX, processed_sample)
            self.myinterpreter.invoke()
            prediction = self.myinterpreter.get_tensor(self.OUTPUT_LAYER_INDEX)[0].copy()

            p_sigmoid = self.custom_sigmoid(prediction, sensitivity)
            detected_birds = [(label, prob) for label, prob in zip(self.CLASSES, p_sigmoid)
                              if label in pantanal_birds and prob > threshold]

            if not detected_birds:
                print("No Pantanal birds detected with probability > threshold.")
            else:
                print("Detected Pantanal birds:", [(label, round(prob, 3)) for label, prob in detected_birds])

            return sorted(detected_birds, key=operator.itemgetter(1), reverse=True)
        except Exception as e:
            print(f"Error during prediction: {e}")
            return []

    def predict_threshold(self, sample, sensitivity=1.0, min_p=0.1, timestamp=0):
        return [p for p in self.predict(sample, sensitivity, threshold=min_p) if p[1] >= min_p]

# Example Usage
if __name__ == "__main__":
    model_path = "model_int8"  # Update with your actual model file name minus '.tflite'
    model = Model(model=model_path)

    # Example input; ensure this matches the expected model input shape
    example_sample = np.random.rand(*model.INPUT_SHAPE).astype(np.float32)  # Adjust based on actual input data format
    results = model.predict(example_sample)
    print("Results:", results)
