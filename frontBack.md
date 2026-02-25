<div class="customCard cardBack">
	<div class="horizontalPadding centerVertically targetWordContainer">
		<span class="targetWord">
			{{Front of Card}}
		</span>
		<span class="wordAudioButtonBack">
			{{word_audio}}
		</span>
	</div>

    <div class="dividerLine"></div>

    <div class="horizontalPadding">
    	<div class="header">
    		definitions:
    	</div>
    	<div class="indent">
    		<ul class="definitionsList">
    			<li>
    				{{Definitions 1}}
    			</li>
    		</ul>
    	</div>
    </div>

    {{#Image}}
    	<div class="image">
    		{{Image}}
    	</div>
    {{/Image}}

    {{^Image}}
    	<div class="dividerLine"></div>
    {{/Image}}

    <div class="horizontalPadding">
    	<div class="header centerVertically">
    		example:
    	</div>
    	<div class="indent">
    		<div class="centerVertically" style="position: relative; gap: 5px;">
    			<span>"{{Example Sentence}}"</span>
    			<span class="sentenceAudioButton">{{sentence_audio}}</span>
    		</div>
    		<div class="sentenceTranslation" id="translation" style="display:none;">{{Translation}}</div>
    	</div>
    </div>

    <div class="dividerLine"></div>

    <div class="horizontalPadding">
    </div>

</div>

Back:
{{FrontSide}}

<script>
document.getElementById('translation').style.display = 'block';
</script>
